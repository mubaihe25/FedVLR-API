from __future__ import annotations

import importlib.util
import json
import re
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

from app.core.settings import Settings, get_settings


SAFE_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class WorkbenchService:
    """Small wrapper around FedVLR's bounded workbench config generator.

    The service intentionally records disabled/pending workbench jobs instead of
    starting long training. This keeps the frontend workflow real without
    claiming that a production task runner is connected.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.output_root = (settings.fedvlr_root / "outputs" / "workbench_jobs").resolve()
        self.generator_path = (settings.fedvlr_root / "scripts" / "generate_workbench_smoke_config.py").resolve()
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
        response = module.write_workbench_job(payload, self.output_root)
        response["source"] = "fedvlr_workbench_generator"
        response["launch_enabled"] = False
        response["message"] = "训练任务启动未接入；已生成受限 smoke 配置和 job 档案。"
        return response

    def get_job(self, job_id: str) -> Dict[str, Any]:
        job_dir = self._safe_job_dir(job_id)
        status = self._read_json(job_dir / "status.json")
        config = self._read_json(job_dir / "config.json")
        return {
            "job_id": job_id,
            "status": status.get("status"),
            "valid": status.get("valid"),
            "created_at": status.get("created_at"),
            "updated_at": status.get("updated_at"),
            "direction": status.get("direction"),
            "scenario_id": status.get("scenario_id"),
            "message": status.get("message"),
            "disabled_reason": status.get("disabled_reason"),
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
        log_path = job_dir / "run.log"
        if not log_path.exists():
            raise FileNotFoundError("run.log")
        bounded_tail = max(1, min(int(tail), 1000))
        lines = log_path.read_text(encoding="utf-8-sig").splitlines()
        return {
            "job_id": job_id,
            "tail": bounded_tail,
            "lines": lines[-bounded_tail:],
            "has_more": len(lines) > bounded_tail,
        }

    def get_result(self, job_id: str) -> Dict[str, Any]:
        job_dir = self._safe_job_dir(job_id)
        pointer = self._read_json(job_dir / "result_pointer.json")
        metrics = self._read_json(job_dir / "metrics_summary.json")
        return {
            "job_id": job_id,
            "status": pointer.get("status"),
            "result_pointer": pointer,
            "metrics_summary": metrics,
            "message": "当前 job 未启动训练；结果页应继续读取已完成 showcase 证据。",
        }


@lru_cache(maxsize=1)
def get_workbench_service() -> WorkbenchService:
    return WorkbenchService(get_settings())
