from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import get_settings
from app.services.launch_registry import LaunchRegistry, get_launch_registry, utc_now


class LauncherService:
    """Minimal launcher wrapper around FedVLR's launch_experiment.py.

    Normal training is started asynchronously with subprocess.Popen so the API
    can return a launch_id immediately. validate_only / dry_run remains a quick
    synchronous call, but it is still written into the same in-memory registry.
    """

    def __init__(self, fedvlr_root: Path, registry: LaunchRegistry) -> None:
        self.fedvlr_root = fedvlr_root
        self.launcher_script = fedvlr_root / "scripts" / "launch_experiment.py"
        self.registry = registry

    def launch(
        self,
        unified_config: Dict[str, Any],
        validate_only: bool = False,
        dry_run: bool = False,
        strict_validation: bool = False,
    ) -> Dict[str, Any]:
        launch_id = uuid.uuid4().hex
        command: List[str] = []
        temp_path: Optional[Path] = None
        launch_mode = "dry_run" if dry_run else "validate_only" if validate_only else "async_train"
        config_summary = self._config_summary(unified_config)

        if not self.fedvlr_root.exists():
            return self._failure_payload(
                launch_id=launch_id,
                launch_mode="unavailable",
                command=command,
                return_code=None,
                config_summary=config_summary,
                validate_only=validate_only,
                dry_run=dry_run,
                strict_validation=strict_validation,
                errors=[f"FedVLR root not found: {self.fedvlr_root}"],
            )
        if not self.launcher_script.exists():
            return self._failure_payload(
                launch_id=launch_id,
                launch_mode="unavailable",
                command=command,
                return_code=None,
                config_summary=config_summary,
                validate_only=validate_only,
                dry_run=dry_run,
                strict_validation=strict_validation,
                errors=[f"FedVLR launcher script not found: {self.launcher_script}"],
            )

        try:
            temp_path = self._write_temp_config(unified_config)
            command = self._build_command(temp_path, validate_only, dry_run, strict_validation)

            if validate_only or dry_run:
                return self._run_validation_launch(
                    launch_id=launch_id,
                    launch_mode=launch_mode,
                    command=command,
                    temp_path=temp_path,
                    config_summary=config_summary,
                    validate_only=validate_only,
                    dry_run=dry_run,
                    strict_validation=strict_validation,
                )

            return self._start_async_launch(
                launch_id=launch_id,
                command=command,
                temp_path=temp_path,
                config_summary=config_summary,
                validate_only=validate_only,
                dry_run=dry_run,
                strict_validation=strict_validation,
            )
        except Exception as exc:  # noqa: BLE001 - API should return a clear launch error.
            if temp_path is not None:
                self._cleanup_temp_file(temp_path)
            return self._failure_payload(
                launch_id=launch_id,
                launch_mode=launch_mode,
                command=command,
                return_code=None,
                config_summary=config_summary,
                validate_only=validate_only,
                dry_run=dry_run,
                strict_validation=strict_validation,
                errors=[f"FedVLR launcher failed to start: {exc}"],
            )

    def get_status(self, launch_id: str) -> Dict[str, Any] | None:
        return self.registry.get(launch_id)

    def _run_validation_launch(
        self,
        launch_id: str,
        launch_mode: str,
        command: List[str],
        temp_path: Path,
        config_summary: Dict[str, Any],
        validate_only: bool,
        dry_run: bool,
        strict_validation: bool,
    ) -> Dict[str, Any]:
        self.registry.create(
            launch_id=launch_id,
            launch_mode=launch_mode,
            command=command,
            config_summary=config_summary,
            validate_only=validate_only,
            dry_run=dry_run,
            strict_validation=strict_validation,
            status="running",
        )
        self.registry.update(launch_id, started_at=utc_now())

        try:
            completed = subprocess.run(
                command,
                cwd=str(self.fedvlr_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout(),
            )
            launcher_payload = self._parse_json_payload(completed.stdout)
            final_fields = self._final_fields_from_output(
                command=command,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                launcher_payload=launcher_payload,
            )
            status = "completed" if final_fields["success"] else "failed"
            return self.registry.update(
                launch_id,
                status=status,
                finished_at=utc_now(),
                **final_fields,
            ) or self._missing_record_payload(launch_id)
        except subprocess.TimeoutExpired as exc:
            return self.registry.update(
                launch_id,
                accepted=False,
                success=False,
                status="failed",
                finished_at=utc_now(),
                return_code=None,
                errors=[f"FedVLR launcher timed out after {exc.timeout} seconds"],
                stdout_tail=self._tail(exc.stdout),
                stderr_tail=self._tail(exc.stderr),
            ) or self._missing_record_payload(launch_id)
        finally:
            self._cleanup_temp_file(temp_path)

    def _start_async_launch(
        self,
        launch_id: str,
        command: List[str],
        temp_path: Path,
        config_summary: Dict[str, Any],
        validate_only: bool,
        dry_run: bool,
        strict_validation: bool,
    ) -> Dict[str, Any]:
        self.registry.create(
            launch_id=launch_id,
            launch_mode="async_train",
            command=command,
            config_summary=config_summary,
            validate_only=validate_only,
            dry_run=dry_run,
            strict_validation=strict_validation,
            status="queued",
        )
        process = subprocess.Popen(
            command,
            cwd=str(self.fedvlr_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.registry.update(
            launch_id,
            status="running",
            started_at=utc_now(),
            pid=process.pid,
            success=True,
        )
        watcher = threading.Thread(
            target=self._watch_process,
            args=(launch_id, command, process, temp_path),
            daemon=True,
        )
        watcher.start()
        return self.registry.get(launch_id) or self._missing_record_payload(launch_id)

    def _watch_process(
        self,
        launch_id: str,
        command: List[str],
        process: subprocess.Popen[str],
        temp_path: Path,
    ) -> None:
        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []

        stdout_thread = threading.Thread(
            target=self._read_stream,
            args=(launch_id, "stdout_tail", process.stdout, stdout_chunks),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._read_stream,
            args=(launch_id, "stderr_tail", process.stderr, stderr_chunks),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        return_code = process.wait()
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        launcher_payload = self._parse_json_payload(stdout)
        final_fields = self._final_fields_from_output(
            command=command,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            launcher_payload=launcher_payload,
        )
        status = "completed" if final_fields["success"] else "failed"
        self.registry.update(
            launch_id,
            status=status,
            finished_at=utc_now(),
            **final_fields,
        )
        self._cleanup_temp_file(temp_path)

    def _read_stream(
        self,
        launch_id: str,
        field_name: str,
        stream: Any,
        chunks: List[str],
    ) -> None:
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                if not line:
                    break
                chunks.append(line)
                self.registry.update(launch_id, **{field_name: self._tail("".join(chunks))})
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _write_temp_config(self, unified_config: Dict[str, Any]) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as temp_file:
            json.dump(unified_config, temp_file, ensure_ascii=False, indent=2)
            return Path(temp_file.name)

    def _build_command(
        self,
        temp_path: Path,
        validate_only: bool,
        dry_run: bool,
        strict_validation: bool,
    ) -> List[str]:
        command = [
            self._python_executable(),
            str(self.launcher_script),
            "--config",
            str(temp_path),
        ]
        if validate_only:
            command.append("--validate-only")
        if dry_run:
            command.append("--dry-run")
        if strict_validation:
            command.append("--strict-validation")
        return command

    def _python_executable(self) -> str:
        env_python = os.getenv("FEDVLR_PYTHON")
        if env_python:
            return env_python

        if os.name == "nt":
            candidate = self.fedvlr_root / ".venv" / "Scripts" / "python.exe"
        else:
            candidate = self.fedvlr_root / ".venv" / "bin" / "python"
        if candidate.exists():
            return str(candidate)
        return sys.executable

    def _timeout(self) -> Optional[int]:
        raw_timeout = os.getenv("FEDVLR_LAUNCH_TIMEOUT_SECONDS", "").strip()
        if not raw_timeout:
            return None
        timeout = int(raw_timeout)
        return timeout if timeout > 0 else None

    def _parse_json_payload(self, stdout: str) -> Dict[str, Any]:
        for index, char in enumerate(stdout):
            if char != "{":
                continue
            candidate = stdout[index:].strip()
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return {}

    def _final_fields_from_output(
        self,
        command: List[str],
        return_code: Optional[int],
        stdout: str,
        stderr: str,
        launcher_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        experiment = launcher_payload.get("experiment", {})
        if not isinstance(experiment, dict):
            experiment = {}
        warnings = launcher_payload.get("warnings", [])
        if not isinstance(warnings, list):
            warnings = []
        errors = launcher_payload.get("errors", [])
        if not isinstance(errors, list):
            errors = []

        success = return_code == 0 and bool(launcher_payload) and bool(launcher_payload.get("ok", True))
        return {
            "accepted": True,
            "success": success,
            "command": command,
            "return_code": return_code,
            "experiment_id": experiment.get("experiment_id"),
            "result_dir": experiment.get("result_dir"),
            "summary_path": experiment.get("summary_path"),
            "result_path": experiment.get("result_path"),
            "csv_path": experiment.get("csv_path"),
            "validation_warnings": warnings,
            "errors": errors,
            "stdout_tail": self._tail(stdout),
            "stderr_tail": self._tail(stderr),
            "launcher_payload": launcher_payload,
        }

    def _failure_payload(
        self,
        launch_id: str,
        launch_mode: str,
        command: List[str],
        return_code: Optional[int],
        config_summary: Dict[str, Any],
        validate_only: bool,
        dry_run: bool,
        strict_validation: bool,
        errors: List[str],
        stdout_tail: Optional[str] = None,
        stderr_tail: Optional[str] = None,
    ) -> Dict[str, Any]:
        record = self.registry.create(
            launch_id=launch_id,
            launch_mode=launch_mode,
            command=command,
            config_summary=config_summary,
            validate_only=validate_only,
            dry_run=dry_run,
            strict_validation=strict_validation,
            status="failed",
        )
        return self.registry.update(
            launch_id,
            accepted=False,
            success=False,
            finished_at=utc_now(),
            return_code=return_code,
            errors=errors,
            stdout_tail=stdout_tail or "",
            stderr_tail=stderr_tail or "",
        ) or record

    def _missing_record_payload(self, launch_id: str) -> Dict[str, Any]:
        return {
            "launch_id": launch_id,
            "accepted": False,
            "success": False,
            "status": "failed",
            "launch_mode": "registry_missing",
            "submitted_at": None,
            "started_at": None,
            "finished_at": utc_now(),
            "pid": None,
            "command": [],
            "return_code": None,
            "experiment_id": None,
            "result_dir": None,
            "summary_path": None,
            "result_path": None,
            "csv_path": None,
            "validation_warnings": [],
            "errors": [f"Launch record not found after update: {launch_id}"],
            "stdout_tail": "",
            "stderr_tail": "",
            "launcher_payload": {},
            "config_summary": {},
            "validate_only": False,
            "dry_run": False,
            "strict_validation": False,
        }

    def _config_summary(self, unified_config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "model": unified_config.get("model"),
            "dataset": unified_config.get("dataset"),
            "scenario": unified_config.get("scenario"),
            "type": unified_config.get("type"),
            "comment": unified_config.get("comment"),
            "enabled_attacks": unified_config.get("enabled_attacks", []),
            "enabled_defenses": unified_config.get("enabled_defenses", []),
            "enabled_privacy_metrics": unified_config.get("enabled_privacy_metrics", []),
            "training_params": unified_config.get("training_params", {}),
            "malicious_client_config": unified_config.get("malicious_client_config", {}),
        }

    def _tail(self, text: Any, max_chars: int = 4000) -> str:
        if text is None:
            return ""
        value = str(text)
        return value[-max_chars:]

    def _cleanup_temp_file(self, temp_path: Path) -> None:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


@lru_cache(maxsize=1)
def get_launcher_service() -> LauncherService:
    settings = get_settings()
    return LauncherService(settings.fedvlr_root, get_launch_registry())
