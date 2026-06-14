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
WORKBENCH_DIRECTION_LABELS = {
    "recommendation_manipulation": "推荐操纵",
    "membership_inference": "成员推断",
    "update_leakage": "更新泄露",
    "aggregation_defense": "聚合防御",
}


class WorkbenchService:
    """Wrapper around FedVLR workbench full-training jobs.

    The only launch path is the whitelisted FedVLR workbench runner. Frontend
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

    def _build_job_metadata(self, payload: Dict[str, Any], direction: str | None, fallback_started_at: str) -> Dict[str, str]:
        raw_started_at = str(payload.get("started_at") or fallback_started_at).strip()
        try:
            started_at_value = datetime.fromisoformat(raw_started_at.replace("Z", "+00:00"))
        except ValueError:
            started_at_value = datetime.fromisoformat(fallback_started_at.replace("Z", "+00:00"))
        if started_at_value.tzinfo is None:
            started_at_value = started_at_value.astimezone()
        started_at_value = started_at_value.replace(microsecond=0)
        direction_label = WORKBENCH_DIRECTION_LABELS.get(str(direction), str(direction or "实验"))
        return {
            "experiment_name": f"{direction_label} · {started_at_value.strftime('%Y-%m-%d %H:%M:%S')}",
            "started_at": started_at_value.isoformat(),
        }

    def _read_job_metadata(self, job_dir: Path) -> Dict[str, Any]:
        metadata_path = job_dir / "metadata.json"
        if not metadata_path.exists():
            return {}
        try:
            metadata = self._read_json(metadata_path)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        return metadata if isinstance(metadata, dict) else {}

    def _repo_relative(self, path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            return path.resolve().relative_to(self.settings.fedvlr_root).as_posix()
        except ValueError:
            return None

    def _job_config_summary(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "model": config.get("model"),
            "dataset": config.get("dataset"),
            "execution_mode": config.get("execution_mode"),
            "requested_execution_mode": config.get("requested_execution_mode"),
            "execution_capability": config.get("execution_capability"),
            "aggregation_mode": config.get("aggregation_mode"),
            "robust_aggregators": config.get("robust_aggregators", []),
            "dp_noise_enabled": config.get("dp_noise_enabled"),
        }

    def _date_matches(self, value: str | None, date_from: str = "", date_to: str = "") -> bool:
        if not value:
            return not date_from and not date_to
        day = value[:10]
        if date_from and day < date_from:
            return False
        if date_to and day > date_to:
            return False
        return True

    def _parse_job_started_at(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    def _is_test_job(self, job_id: str, experiment_name: Any) -> bool:
        normalized_job_id = job_id.strip().lower()
        normalized_name = str(experiment_name or "").strip().lower()
        return (
            "test" in normalized_job_id
            or "test" in normalized_name
            or normalized_job_id.startswith("codex_")
            or normalized_name.startswith("codex_")
        )

    def _compact_metrics(self, metrics_summary: Dict[str, Any] | None) -> Dict[str, Any]:
        if not isinstance(metrics_summary, dict):
            return {}
        metrics = metrics_summary.get("metrics")
        if not isinstance(metrics, dict):
            metrics = metrics_summary
        keep = [
            "baseline_unmasked_rank",
            "attack_unmasked_rank",
            "rank_gain",
            "attack_topk_hit",
            "target_manipulation_index",
            "recommendation_jaccard",
            "auc",
            "accuracy",
            "score_gap",
            "evidence_type",
            "hit_at_10",
            "hit_at_20",
            "hit_at_50",
            "highest_risk_modality",
            "recall_at_50",
            "ndcg_at_50",
            "defense_algorithm",
            "recovery_rate_recall",
            "recovery_rate_ndcg",
            "selected_client_count",
            "rejected_client_count",
        ]
        compact: Dict[str, Any] = {}
        for key in keep:
            value = metrics.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact[key] = value
        return {key: value for key, value in compact.items() if value is not None}

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
        normalized_payload = dict(payload)
        normalized_payload.setdefault("execution_mode", "full_train")
        response = module.validation_response(normalized_payload)
        response["source"] = "fedvlr_workbench_generator"
        return response

    def create_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        module = self._load_generator()
        if not self.runner_path.exists():
            raise FileNotFoundError("FedVLR workbench runner is missing")

        normalized_payload = dict(payload)
        normalized_payload.setdefault("execution_mode", "full_train")
        response = module.validation_response(normalized_payload)
        response["source"] = "fedvlr_workbench_generator"
        if not response.get("valid"):
            field_messages = []
            field_errors = response.get("field_errors") or {}
            if isinstance(field_errors, dict):
                for field, messages in field_errors.items():
                    if isinstance(messages, list):
                        field_messages.extend(f"{field}: {message}" for message in messages)
            response["launch_enabled"] = False
            response["message"] = "配置未通过校验，未创建全量训练任务。"
            response["error_message"] = "；".join([*field_messages, *(str(item) for item in response.get("errors", []))]) or "配置未通过校验。"
            return response

        job_id = module.safe_job_id(str(payload.get("job_id")) if payload.get("job_id") else None)
        job_dir = self._safe_job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        created_at = self._utc_now()
        payload_path = job_dir / "payload.json"
        normalized_config = response.get("normalized_config", {})
        metadata = self._build_job_metadata(normalized_payload, normalized_config.get("direction"), created_at)
        normalized_payload.update(metadata)

        self._write_json(payload_path, normalized_payload)
        self._write_json(job_dir / "config.json", normalized_config)
        self._write_json(job_dir / "metadata.json", metadata)
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
                "started_at": metadata["started_at"],
                "finished_at": None,
                "experiment_name": metadata["experiment_name"],
                "direction": normalized_config.get("direction"),
                "execution_mode": normalized_config.get("execution_mode"),
                "requested_execution_mode": normalized_config.get("requested_execution_mode"),
                "scenario_id": normalized_config.get("scenario_id"),
                "message": "真实全量训练任务已进入队列。",
                "error_message": None,
                "result_dir": None,
                "artifact_dir": None,
                "source": None,
                "runner_pid": None,
                "pid": None,
                "return_code": None,
                "subprocess_command": None,
                "python_path": str(self._workbench_python()),
                "cwd": str(self.settings.fedvlr_root),
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
        status_payload = self._read_json(job_dir / "status.json")
        status_payload.update(
            {
                "runner_pid": process.pid,
                "runner_command": subprocess.list2cmdline(command),
                "python_path": str(self._workbench_python()),
                "cwd": str(self.settings.fedvlr_root),
                "updated_at": self._utc_now(),
            }
        )
        self._write_json(job_dir / "status.json", status_payload)

        response.update(
            {
                "job_id": job_id,
                "job_status": "queued",
                "status": "queued",
                "stage": "queued",
                "progress": 0,
                "experiment_name": metadata["experiment_name"],
                "started_at": metadata["started_at"],
                "job_dir": self._repo_relative(job_dir),
                "pid": process.pid,
                "launch_enabled": True,
                "message": "已启动真实全量训练任务，正在准备配置。",
                "files": {
                    "payload": "payload.json",
                    "config": "config.json",
                    "metadata": "metadata.json",
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
        metadata = self._read_job_metadata(job_dir)
        config_summary = self._job_config_summary(config)
        return {
            "job_id": job_id,
            "status": status.get("status"),
            "stage": status.get("stage"),
            "progress": status.get("progress"),
            "valid": status.get("valid"),
            "created_at": status.get("created_at"),
            "updated_at": status.get("updated_at"),
            "started_at": metadata.get("started_at") or status.get("started_at"),
            "finished_at": status.get("finished_at"),
            "experiment_name": metadata.get("experiment_name") or status.get("experiment_name"),
            "direction": status.get("direction"),
            "dataset": config.get("dataset"),
            "model": config.get("model"),
            "execution_mode": status.get("execution_mode") or config.get("execution_mode"),
            "requested_execution_mode": status.get("requested_execution_mode") or config.get("requested_execution_mode"),
            "scenario_id": status.get("scenario_id"),
            "message": status.get("message"),
            "error_message": status.get("error_message"),
            "error_summary": status.get("error_summary"),
            "error_detail": status.get("error_detail"),
            "failure_stage": status.get("failure_stage"),
            "runner_pid": status.get("runner_pid"),
            "pid": status.get("pid"),
            "return_code": status.get("return_code"),
            "subprocess_command": status.get("subprocess_command"),
            "python_path": status.get("python_path"),
            "cwd": status.get("cwd"),
            "result_dir": status.get("result_dir"),
            "artifact_dir": status.get("artifact_dir"),
            "source": status.get("source"),
            "warnings": status.get("warnings", []),
            "errors": status.get("errors", []),
            "config_summary": config_summary,
        }

    def list_jobs(
        self,
        *,
        limit: int = 12,
        page: int = 1,
        direction: str = "",
        dataset: str = "",
        model: str = "",
        source: str = "",
        status: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> Dict[str, Any]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        bounded_limit = max(1, min(int(limit), 100))
        bounded_page = max(1, int(page))
        items = []
        for job_dir in self.output_root.iterdir():
            if not job_dir.is_dir():
                continue
            status_path = job_dir / "status.json"
            if not status_path.exists():
                continue
            try:
                status_payload = self._read_json(status_path)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            config = self._read_json(job_dir / "config.json") if (job_dir / "config.json").exists() else {}
            metadata = self._read_job_metadata(job_dir)
            metrics_summary = self._read_json(job_dir / "metrics_summary.json") if (job_dir / "metrics_summary.json").exists() else {}
            job_id = str(status_payload.get("job_id") or job_dir.name)
            experiment_name = metadata.get("experiment_name") or status_payload.get("experiment_name")
            started_at = metadata.get("started_at") or status_payload.get("started_at")
            parsed_started_at = self._parse_job_started_at(started_at)
            if self._is_test_job(job_id, experiment_name) or parsed_started_at is None:
                continue
            item = {
                "job_id": job_id,
                "experiment_name": experiment_name,
                "direction": status_payload.get("direction") or config.get("direction"),
                "dataset": config.get("dataset"),
                "model": config.get("model"),
                "execution_mode": status_payload.get("execution_mode") or config.get("execution_mode"),
                "requested_execution_mode": status_payload.get("requested_execution_mode") or config.get("requested_execution_mode"),
                "source": status_payload.get("source") or metrics_summary.get("source"),
                "status": status_payload.get("status"),
                "created_at": status_payload.get("created_at"),
                "started_at": started_at,
                "finished_at": status_payload.get("finished_at"),
                "failure_stage": status_payload.get("failure_stage"),
                "error_summary": status_payload.get("error_summary"),
                "error_detail": status_payload.get("error_detail"),
                "return_code": status_payload.get("return_code"),
                "key_metrics": self._compact_metrics(metrics_summary),
                "result_dir": status_payload.get("result_dir"),
                "artifact_dir": status_payload.get("artifact_dir"),
            }
            if direction and item["direction"] != direction:
                continue
            if dataset and item["dataset"] != dataset:
                continue
            if model and item["model"] != model:
                continue
            if source and item["source"] != source:
                continue
            if status and item["status"] != status:
                continue
            if not self._date_matches(str(item.get("started_at") or item.get("created_at") or ""), date_from=date_from, date_to=date_to):
                continue
            items.append((parsed_started_at, item))
        items.sort(key=lambda entry: entry[0], reverse=True)
        sorted_items = [item for _, item in items]
        total = len(sorted_items)
        start = (bounded_page - 1) * bounded_limit
        end = start + bounded_limit
        return {
            "items": sorted_items[start:end],
            "page": bounded_page,
            "limit": bounded_limit,
            "total": total,
            "total_pages": max(1, (total + bounded_limit - 1) // bounded_limit),
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
            "message": "结果来自真实全量训练任务。",
        }


@lru_cache(maxsize=1)
def get_workbench_service() -> WorkbenchService:
    return WorkbenchService(get_settings())
