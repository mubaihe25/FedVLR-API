from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

from app.core.settings import Settings, get_settings


SAFE_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class WorkbenchService:
    """Wrapper around FedVLR bounded workbench smoke jobs.

    The only launch path is the whitelisted FedVLR smoke runner. Frontend
    payloads are validated by the FedVLR schema generator and are never treated
    as shell commands.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.output_root = (settings.fedvlr_root / "outputs" / "workbench_jobs").resolve()
        self.generator_path = (settings.fedvlr_root / "scripts" / "generate_workbench_smoke_config.py").resolve()
        self.runner_path = (settings.fedvlr_root / "scripts" / "run_workbench_smoke_job.py").resolve()
        self._module: ModuleType | None = None

    def _load_generator(self) -> ModuleType:
        if self._module is not None:
            return self._module
        if not self.generator_path.exists():
            raise FileNotFoundError("FedVLR workbench generator is missing")
        spec = importlib.util.spec_from_file_location("fedvlr_workbench_generator", self.generator_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load FedVLR workbench generator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._module = module
        return module

    def _safe_job_dir(self, job_id: str) -> Path:
        if not SAFE_JOB_ID_RE.fullmatch(job_id):
            raise ValueError("invalid_job_id")
        job_dir = (self.output_root / job_id).resolve()
        if self.output_root not in [job_dir, *job_dir.parents]:
            raise ValueError("job_path_outside_workbench_root")
        return job_dir

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            raise FileNotFoundError(path.name)
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _repo_relative(self, path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            return path.resolve().relative_to(self.settings.fedvlr_root).as_posix()
        except ValueError:
            return None

    def _workbench_python(self) -> Path | str:
        env_path = os.getenv("FEDVLR_PYTHON")
        if env_path:
            return Path(env_path).expanduser()
        venv_python = self.settings.fedvlr_root / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return venv_python
        return sys.executable

    def options(self) -> Dict[str, Any]:
        module = self._load_generator()
        payload = module.get_workbench_options()
        payload["source"] = "fedvlr_workbench_schema"
        return payload

    def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        module = self._load_generator()
        response = module.validation_response(payload)
        response["source"] = "fedvlr_workbench_generator"
        return response

    def create_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        module = self._load_generator()
        if not self.runner_path.exists():
            raise FileNotFoundError("FedVLR workbench smoke runner is missing")

        response = module.validation_response(payload)
        response["source"] = "fedvlr_workbench_generator"
        if not response.get("valid"):
            field_messages = []
            field_errors = response.get("field_errors") or {}
            if isinstance(field_errors, dict):
                for field, messages in field_errors.items():
                    if isinstance(messages, list):
                        field_messages.extend(f"{field}: {message}" for message in messages)
            response["launch_enabled"] = False
            response["message"] = "配置未通过校验，未创建 smoke job。"
            response["error_message"] = "；".join([*field_messages, *(str(item) for item in response.get("errors", []))]) or "配置未通过校验。"
            return response

        job_id = module.safe_job_id(str(payload.get("job_id")) if payload.get("job_id") else None)
        job_dir = self._safe_job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        created_at = self._utc_now()
        payload_path = job_dir / "payload.json"

        self._write_json(payload_path, payload)
        self._write_json(job_dir / "config.json", response.get("normalized_config", {}))
        self._write_json(
            job_dir / "status.json",
            {
                "job_id": job_id,
                "status": "queued",
                "stage": "queued",
                "progress": 0,
                "valid": True,
                "created_at": created_at,
                "updated_at": created_at,
                "started_at": None,
                "finished_at": None,
                "direction": response.get("normalized_config", {}).get("direction"),
                "scenario_id": response.get("normalized_config", {}).get("scenario_id"),
                "message": "受限 smoke job 已进入队列。",
                "error_message": None,
                "result_dir": None,
                "artifact_dir": None,
                "source": None,
                "warnings": response.get("warnings", []),
                "errors": [],
            },
        )
        (job_dir / "run.log").write_text(f"[{created_at}] Workbench job {job_id} queued by API.\n", encoding="utf-8")

        command = [
            str(self._workbench_python()),
            str(self.runner_path),
            "--job-id",
            job_id,
            "--payload-file",
            str(payload_path),
            "--output-dir",
            str(self.output_root),
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        process = subprocess.Popen(  # noqa: S603 - fixed Python executable and whitelisted runner path.
            command,
            cwd=str(self.settings.fedvlr_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )

        response.update(
            {
                "job_id": job_id,
                "job_status": "queued",
                "status": "queued",
                "stage": "queued",
                "progress": 0,
                "job_dir": self._repo_relative(job_dir),
                "pid": process.pid,
                "launch_enabled": True,
                "message": "已启动受限 smoke job，正在准备配置。",
                "files": {
                    "payload": "payload.json",
                    "config": "config.json",
                    "status": "status.json",
                    "log": "run.log",
                    "result_pointer": "result_pointer.json",
                    "metrics_summary": "metrics_summary.json",
                },
            }
        )
        return response

    def get_job(self, job_id: str) -> Dict[str, Any]:
        job_dir = self._safe_job_dir(job_id)
        status = self._read_json(job_dir / "status.json")
        config = self._read_json(job_dir / "config.json") if (job_dir / "config.json").exists() else {}
        return {
            "job_id": job_id,
            "status": status.get("status"),
            "stage": status.get("stage"),
            "progress": status.get("progress"),
            "valid": status.get("valid"),
            "created_at": status.get("created_at"),
            "updated_at": status.get("updated_at"),
            "started_at": status.get("started_at"),
            "finished_at": status.get("finished_at"),
            "direction": status.get("direction"),
            "scenario_id": status.get("scenario_id"),
            "message": status.get("message"),
            "error_message": status.get("error_message"),
            "result_dir": status.get("result_dir"),
            "artifact_dir": status.get("artifact_dir"),
            "source": status.get("source"),
            "warnings": status.get("warnings", []),
            "errors": status.get("errors", []),
            "config_summary": {
                "model": config.get("model"),
                "dataset": config.get("dataset"),
                "aggregation_mode": config.get("aggregation_mode"),
                "robust_aggregators": config.get("robust_aggregators", []),
                "dp_noise_enabled": config.get("dp_noise_enabled"),
            },
        }

    def get_logs(self, job_id: str, tail: int = 200) -> Dict[str, Any]:
        job_dir = self._safe_job_dir(job_id)
        if not job_dir.exists():
            raise FileNotFoundError(job_id)
        bounded_tail = max(1, min(int(tail), 1000))
        log_path = job_dir / "run.log"
        if not log_path.exists():
            return {
                "job_id": job_id,
                "tail": bounded_tail,
                "lines": [],
                "has_more": False,
            }
        lines = log_path.read_text(encoding="utf-8-sig").splitlines()
        return {
            "job_id": job_id,
            "tail": bounded_tail,
            "lines": lines[-bounded_tail:],
            "has_more": len(lines) > bounded_tail,
        }

    def get_result(self, job_id: str) -> Dict[str, Any]:
        job_dir = self._safe_job_dir(job_id)
        status = self._read_json(job_dir / "status.json")
        pointer = self._read_json(job_dir / "result_pointer.json") if (job_dir / "result_pointer.json").exists() else None
        metrics = self._read_json(job_dir / "metrics_summary.json") if (job_dir / "metrics_summary.json").exists() else None
        return {
            "job_id": job_id,
            "status": (pointer or {}).get("status") or status.get("status"),
            "stage": status.get("stage"),
            "source": (pointer or {}).get("source") or status.get("source"),
            "result_pointer": pointer,
            "metrics_summary": metrics,
            "message": "结果来自受限 smoke job；source=existing_artifact 时表示复用已导出的证据。",
        }


@lru_cache(maxsize=1)
def get_workbench_service() -> WorkbenchService:
    return WorkbenchService(get_settings())
