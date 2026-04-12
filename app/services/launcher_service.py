from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import get_settings


class LauncherService:
    """Minimal synchronous wrapper around FedVLR's launch_experiment.py."""

    def __init__(self, fedvlr_root: Path) -> None:
        self.fedvlr_root = fedvlr_root
        self.launcher_script = fedvlr_root / "scripts" / "launch_experiment.py"

    def launch(
        self,
        unified_config: Dict[str, Any],
        validate_only: bool = False,
        dry_run: bool = False,
        strict_validation: bool = False,
    ) -> Dict[str, Any]:
        if not self.fedvlr_root.exists():
            return self._failure_payload(
                command=[],
                return_code=None,
                errors=[f"FedVLR root not found: {self.fedvlr_root}"],
            )
        if not self.launcher_script.exists():
            return self._failure_payload(
                command=[],
                return_code=None,
                errors=[f"FedVLR launcher script not found: {self.launcher_script}"],
            )

        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".json",
                delete=False,
            ) as temp_file:
                json.dump(unified_config, temp_file, ensure_ascii=False, indent=2)
                temp_path = Path(temp_file.name)

            command = [
                self._python_executable(),
                str(self.launcher_script),
                "--config",
                str(temp_path),
            ]
            if validate_only or dry_run:
                command.append("--validate-only")
            if strict_validation:
                command.append("--strict-validation")

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
            return self._build_response(command, completed, launcher_payload)
        except subprocess.TimeoutExpired as exc:
            return self._failure_payload(
                command=exc.cmd if isinstance(exc.cmd, list) else [],
                return_code=None,
                errors=[f"FedVLR launcher timed out after {exc.timeout} seconds"],
                stdout_tail=self._tail(exc.stdout),
                stderr_tail=self._tail(exc.stderr),
            )
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

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

    def _build_response(
        self,
        command: List[str],
        completed: subprocess.CompletedProcess[str],
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

        return {
            "accepted": True,
            "success": completed.returncode == 0
            and bool(launcher_payload)
            and bool(launcher_payload.get("ok", True)),
            "launch_mode": "validate_only"
            if "--validate-only" in command
            else "sync_train",
            "command": command,
            "return_code": completed.returncode,
            "experiment_id": experiment.get("experiment_id"),
            "result_dir": experiment.get("result_dir"),
            "summary_path": experiment.get("summary_path"),
            "result_path": experiment.get("result_path"),
            "csv_path": experiment.get("csv_path"),
            "validation_warnings": warnings,
            "errors": errors,
            "stdout_tail": self._tail(completed.stdout),
            "stderr_tail": self._tail(completed.stderr),
            "launcher_payload": launcher_payload,
        }

    def _failure_payload(
        self,
        command: List[str],
        return_code: Optional[int],
        errors: List[str],
        stdout_tail: Optional[str] = None,
        stderr_tail: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "accepted": False,
            "success": False,
            "launch_mode": "unavailable",
            "command": command,
            "return_code": return_code,
            "experiment_id": None,
            "result_dir": None,
            "summary_path": None,
            "result_path": None,
            "csv_path": None,
            "validation_warnings": [],
            "errors": errors,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "launcher_payload": {},
        }

    def _tail(self, text: Any, max_chars: int = 4000) -> str:
        if text is None:
            return ""
        value = str(text)
        return value[-max_chars:]


@lru_cache(maxsize=1)
def get_launcher_service() -> LauncherService:
    settings = get_settings()
    return LauncherService(settings.fedvlr_root)
