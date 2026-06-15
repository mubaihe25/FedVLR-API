from __future__ import annotations

import importlib.util
import hashlib
import csv
import json
import os
import re
import subprocess
import sys
import time
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

# 运行时性能参数 — 收口为后端固定安全默认值。
# 不再作为 Workbench 前端可编辑 / 可提交字段；旧 payload 传值会被覆盖。
# 顺序与 FedVLR/configs/workbench_experiment_schema.json 的 runtime_parameters 收口策略保持一致。
WORKBENCH_RUNTIME_LOCKED_KEYS = (
    "num_workers",
    "prefetch_factor",
    "pin_memory",
    "persistent_workers",
    "amp_enabled",
    "cache_item_features_on_device",
    "non_blocking_transfer",
    "reuse_client_model_workspace",
)
WORKBENCH_RUNTIME_SAFE_DEFAULTS: Dict[str, Any] = {
    "num_workers": 0,
    "prefetch_factor": None,
    "pin_memory": False,
    "persistent_workers": False,
    "amp_enabled": False,
    "cache_item_features_on_device": True,
    "non_blocking_transfer": True,
    "reuse_client_model_workspace": True,
}


def coerce_runtime_safety(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    """把工作台 payload 中的运行时性能参数统一收口为安全默认值。

    - 不论调用方是否传了 8 个字段，全部覆盖为 ``WORKBENCH_RUNTIME_SAFE_DEFAULTS``；
    - 即便旧前端或 curl 显式提交，模型/训练链路也只会读到安全值；
    - 兼容驼峰 / 下划线 / 大小写变体。
    """
    if not isinstance(payload, dict):
        return {}
    for key in WORKBENCH_RUNTIME_LOCKED_KEYS:
        camel = "".join(part.capitalize() if index else part for index, part in enumerate(key.split("_")))
        for variant in (key, camel, camel.upper(), key.upper()):
            if variant in payload:
                payload.pop(variant, None)
        payload[key] = WORKBENCH_RUNTIME_SAFE_DEFAULTS[key]
    return payload


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
        self.preflight_path = (settings.fedvlr_root / "scripts" / "workbench_forward_preflight.py").resolve()
        self._module: ModuleType | None = None
        self._preflight_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}

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
        defense = config.get("defense") if isinstance(config.get("defense"), dict) else {}
        return {
            "model": config.get("model"),
            "dataset": config.get("dataset"),
            "execution_mode": config.get("execution_mode"),
            "requested_execution_mode": config.get("requested_execution_mode"),
            "execution_capability": config.get("execution_capability"),
            "aggregation_mode": config.get("aggregation_mode"),
            "robust_aggregators": config.get("robust_aggregators", []),
            "dp_noise_enabled": config.get("dp_noise_enabled"),
            "base_attack": defense.get("base_attack"),
            "defense_algorithm": (config.get("robust_aggregators") or [None])[0],
        }

    def _read_progress(self, job_dir: Path, status: Dict[str, Any]) -> Dict[str, Any] | None:
        progress_path = job_dir / "progress.json"
        progress = self._read_json(progress_path) if progress_path.exists() else None
        if not isinstance(progress, dict):
            if status.get("status") in {"completed", "partial"}:
                return {
                    "phase": "completed",
                    "phase_label": "实验完成",
                    "current_epoch": 0,
                    "total_epochs": 0,
                    "current_client": 0,
                    "total_clients": 0,
                    "completed_clients": 0,
                    "percent": 100.0,
                    "updated_at": status.get("updated_at"),
                    "elapsed_seconds": None,
                    "estimated_remaining_seconds": 0,
                }
            return None
        progress.pop("started_timestamp", None)
        if status.get("status") in {"completed", "partial"}:
            progress["percent"] = 100.0
            progress["phase"] = "completed"
            progress["phase_label"] = "实验完成"
            progress["estimated_remaining_seconds"] = 0
        elif status.get("status") == "failed":
            progress["failure_phase"] = status.get("failure_stage") or progress.get("phase")
            progress["phase"] = "failed"
            progress["phase_label"] = "实验失败"
            progress["estimated_remaining_seconds"] = None
        return progress

    def _read_gpu_stats(self, job_dir: Path, limit: int = 60) -> Dict[str, Any]:
        path = job_dir / "gpu_stats.csv"
        if not path.exists():
            return {"available": False, "samples": [], "latest": None}
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except (OSError, csv.Error):
            return {"available": False, "samples": [], "latest": None}
        samples = []
        for row in rows[-max(1, min(limit, 300)):]:
            try:
                samples.append(
                    {
                        "timestamp": row.get("timestamp"),
                        "utilization_gpu": float(row["utilization_gpu"]),
                        "memory_used": float(row["memory_used"]),
                        "memory_total": float(row["memory_total"]),
                        "power_draw": float(row["power_draw"]),
                        "temperature": float(row["temperature"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        return {"available": bool(samples), "samples": samples, "latest": samples[-1] if samples else None}

    def _read_epoch_metrics(self, job_dir: Path) -> Dict[str, Any]:
        path = job_dir / "epoch_metrics.json"
        payload = self._read_json(path) if path.exists() else {}
        if not isinstance(payload, dict):
            return {}
        return {
            str(phase): records
            for phase, records in payload.items()
            if isinstance(records, list)
        }

    def _shape_failure_fields(self, status: Dict[str, Any]) -> Dict[str, Any]:
        actual = status.get("actual_tensor_shapes") or status.get("actual_tensor_shape")
        expected = status.get("model_expected_shapes") or status.get("model_expected_shape")
        detail = str(status.get("error_detail") or status.get("error_summary") or "")
        if actual is None:
            match = re.search(r"actual_tensor_shape=([^;\n]+)", detail)
            if match:
                actual = match.group(1).strip()
        if expected is None:
            match = re.search(r"model_expected_shape=([^;\n]+)", detail)
            if match:
                expected = match.group(1).strip()
        if actual is None or expected is None:
            match = re.search(
                r"mat1 and mat2 shapes cannot be multiplied \((\d+)x(\d+) and (\d+)x(\d+)\)",
                detail,
            )
            if match:
                actual = actual or f"({match.group(1)}, {match.group(2)})"
                expected = expected or f"(*, {match.group(3)})"
        return {
            "actual_tensor_shapes": actual,
            "model_expected_shapes": expected,
        }

    def _safe_relative_string(self, value: str) -> str | None:
        root_text = str(self.settings.fedvlr_root)
        value = value.replace(root_text, ".").replace(root_text.replace("\\", "/"), ".")
        normalized = value.replace("\\", "/")
        if re.match(r"^[A-Za-z]:/", normalized) or normalized.startswith("//"):
            try:
                return Path(value).resolve().relative_to(self.settings.fedvlr_root).as_posix()
            except (ValueError, OSError):
                return None
        return re.sub(r"[A-Za-z]:[/\\][^\s\"']+", "<local-path>", value)

    def _sanitize_payload(self, value: Any, *, key: str = "") -> Any:
        if isinstance(value, dict):
            sanitized: Dict[str, Any] = {}
            for child_key, child_value in value.items():
                cleaned = self._sanitize_payload(child_value, key=str(child_key))
                if cleaned is not None or child_value is None:
                    sanitized[str(child_key)] = cleaned
            return sanitized
        if isinstance(value, list):
            limits = {
                "candidates": 50,
                "candidate_scores": 50,
                "roc_curve": 200,
                "rounds": 100,
                "rejected_client_ids": 100,
            }
            limit = limits.get(key, 500)
            return [self._sanitize_payload(item, key=key) for item in value[:limit]]
        if isinstance(value, str):
            return self._safe_relative_string(value)
        return value

    def _normalize_result(self, job_id: str, status: Dict[str, Any], metrics: Dict[str, Any] | None) -> Dict[str, Any] | None:
        if not isinstance(metrics, dict):
            return None
        if metrics.get("schema_version") == "workbench-result-v2":
            return self._sanitize_payload(metrics)
        legacy_metrics = metrics.get("metrics") if isinstance(metrics.get("metrics"), dict) else {}
        direction = metrics.get("direction") or status.get("direction")
        normalized = {
            "schema_version": "workbench-result-v2",
            "job_id": job_id,
            "direction": direction,
            "dataset": metrics.get("dataset") or legacy_metrics.get("dataset"),
            "model": metrics.get("model") or legacy_metrics.get("model"),
            "status": metrics.get("status") or status.get("status"),
            "source": metrics.get("source") or status.get("source"),
            "started_at": status.get("started_at") or status.get("created_at"),
            "finished_at": status.get("finished_at"),
            "config_summary": {},
            "training": {
                "loss": legacy_metrics.get("loss"),
                "recall_at_50": legacy_metrics.get("recall_at_50"),
                "ndcg_at_50": legacy_metrics.get("ndcg_at_50"),
                "epochs": legacy_metrics.get("epochs"),
                "rounds": [],
            },
            "direction_result": legacy_metrics,
            "metrics": legacy_metrics,
            "warnings": metrics.get("warnings", []),
            "missing_evidence": [],
            "partial_reason": metrics.get("partial_reason"),
        }
        return self._sanitize_payload(normalized)

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
        direction = str(metrics_summary.get("direction") or "")
        direction_result = metrics_summary.get("direction_result")
        metrics = direction_result if isinstance(direction_result, dict) else metrics_summary.get("metrics")
        if not isinstance(metrics, dict):
            metrics = metrics_summary
        if direction == "recommendation_manipulation":
            return {
                key: value
                for key, value in {
                    "baseline_target_rank": metrics.get("baseline_target_rank", metrics.get("baseline_unmasked_rank")),
                    "attack_target_rank": metrics.get("attack_target_rank", metrics.get("attack_unmasked_rank")),
                    "defended_target_rank": metrics.get("defended_target_rank", metrics.get("defense_unmasked_rank")),
                    "rank_gain": metrics.get("rank_gain"),
                    "attack_top50_hit": metrics.get("attack_top50_hit", metrics.get("attack_topk_hit")),
                    "defended_top50_hit": metrics.get("defended_top50_hit"),
                    "final_top50_hit": metrics.get("masked_top50_hit"),
                    "top50_hit_count": metrics.get("top50_hit_count", metrics.get("masked_top50_hit_count")),
                    "top50_hit_rate": metrics.get("top50_hit_rate", metrics.get("masked_top50_hit_rate")),
                    "audited_user_count": metrics.get("audited_user_count", metrics.get("evaluated_user_count")),
                    "attack_vs_baseline_jaccard": metrics.get("attack_vs_baseline_jaccard"),
                    "defense_vs_baseline_jaccard": metrics.get("defense_vs_baseline_jaccard"),
                    "result_variant": metrics.get("result_variant"),
                    "robust_aggregator": metrics.get("robust_aggregator"),
                    "target_manipulation_index": metrics.get("target_manipulation_index"),
                }.items()
                if value is not None
            }
        if direction == "membership_inference":
            return {key: value for key, value in {"auc": metrics.get("auc"), "accuracy": metrics.get("accuracy")}.items() if value is not None}
        if direction == "update_leakage":
            return {
                key: value
                for key, value in {
                    "hit_at_10": metrics.get("hit_at_10"),
                    "hit_at_20": metrics.get("hit_at_20"),
                    "hit_at_50": metrics.get("hit_at_50"),
                }.items()
                if value is not None
            }
        if direction == "aggregation_defense":
            defended = metrics.get("defended") if isinstance(metrics.get("defended"), dict) else {}
            return {
                key: value
                for key, value in {
                    "defended_recall_at_50": defended.get("recall_at_50", metrics.get("defended_recall_at_50")),
                    "defended_ndcg_at_50": defended.get("ndcg_at_50", metrics.get("defended_ndcg_at_50")),
                    "recovery_rate_recall": metrics.get("recovery_rate_recall"),
                    "rejected_client_count": metrics.get("rejected_client_count"),
                }.items()
                if value is not None
            }
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

    def _preflight_cache_key(self, payload: Dict[str, Any]) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _run_forward_preflight(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.preflight_path.exists():
            raise FileNotFoundError("FedVLR forward preflight is missing")
        cache_key = self._preflight_cache_key(payload)
        cached = self._preflight_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] <= 300:
            return dict(cached[1])
        command = [
            str(self._workbench_python()),
            str(self.preflight_path),
            "--stdin",
        ]
        completed = subprocess.run(  # noqa: S603 - fixed Python executable and whitelisted preflight path.
            command,
            cwd=str(self.settings.fedvlr_root),
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        stdout_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        try:
            result = json.loads(stdout_lines[-1]) if stdout_lines else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"FedVLR forward preflight returned invalid JSON: {completed.stderr.strip()}"
            ) from exc
        if not isinstance(result, dict):
            raise RuntimeError("FedVLR forward preflight returned a non-object response")
        result.setdefault("return_code", completed.returncode)
        if completed.returncode != 0:
            result["valid"] = False
            result.setdefault("failure_stage", "forward_preflight")
            result.setdefault("error_summary", "真实最小 forward 预检失败。")
            result.setdefault("error_detail", completed.stderr.strip() or completed.stdout.strip())
        self._preflight_cache[cache_key] = (time.monotonic(), dict(result))
        return result

    def _validation_with_preflight(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        module = self._load_generator()
        normalized_payload = dict(payload)
        # 运行时性能参数（num_workers / prefetch_factor / pin_memory /
        # persistent_workers / amp_enabled / cache_item_features_on_device /
        # non_blocking_transfer / reuse_client_model_workspace）已收口为
        # WORKBENCH_RUNTIME_SAFE_DEFAULTS；忽略/覆盖旧 payload 里的任何值，
        # 即便旧前端或 curl 显式提交也只会进安全值。
        coerce_runtime_safety(normalized_payload)
        normalized_payload.setdefault("execution_mode", "full_train")
        response = module.validation_response(normalized_payload)
        response["source"] = "fedvlr_workbench_generator"
        if not response.get("valid"):
            return response

        preflight = self._run_forward_preflight(normalized_payload)
        response["forward_preflight"] = preflight
        if preflight.get("valid"):
            normalized_config = response.get("normalized_config")
            if isinstance(normalized_config, dict):
                capability = normalized_config.get("execution_capability")
                if isinstance(capability, dict):
                    capability.update(preflight.get("verification") or {})
            return response

        response["valid"] = False
        response["status"] = "invalid"
        response["launch_enabled"] = False
        preflight_errors = [str(item) for item in preflight.get("errors") or []]
        response["errors"] = list(dict.fromkeys([*(response.get("errors") or []), *preflight_errors]))
        field_errors = dict(response.get("field_errors") or {})
        for field, messages in (preflight.get("field_errors") or {}).items():
            field_errors.setdefault(field, []).extend(str(item) for item in messages)
            field_errors[field] = list(dict.fromkeys(field_errors[field]))
        response["field_errors"] = field_errors
        response["failure_stage"] = preflight.get("failure_stage") or "forward_preflight"
        response["error_summary"] = preflight.get("error_summary") or "真实最小 forward 预检失败。"
        response["error_detail"] = preflight.get("error_detail")
        response["actual_tensor_shapes"] = preflight.get("actual_tensor_shapes")
        response["model_expected_shapes"] = preflight.get("model_expected_shapes")
        response["return_code"] = preflight.get("return_code")
        response["error_message"] = response["error_summary"]
        return response

    def options(self) -> Dict[str, Any]:
        module = self._load_generator()
        payload = module.get_workbench_options()
        payload["source"] = "fedvlr_workbench_schema"
        # 运行时性能参数已收口为后端固定默认值，不再作为前端参数返回。
        # 从 /workbench/options 的 parameter_descriptors / allowed_params /
        # defaults 中剔除，避免旧前端 / 调试脚本误用。
        parameter_descriptors = payload.get("parameter_descriptors")
        if isinstance(parameter_descriptors, dict):
            for key in WORKBENCH_RUNTIME_LOCKED_KEYS:
                parameter_descriptors.pop(key, None)
        allowed_params = payload.get("allowed_params")
        if isinstance(allowed_params, list):
            payload["allowed_params"] = [
                item for item in allowed_params
                if not (isinstance(item, str) and item in WORKBENCH_RUNTIME_LOCKED_KEYS)
            ]
        defaults = payload.get("defaults")
        if isinstance(defaults, dict):
            for key in WORKBENCH_RUNTIME_LOCKED_KEYS:
                defaults.pop(key, None)
        return payload

    def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._validation_with_preflight(payload)

    def create_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        module = self._load_generator()
        if not self.runner_path.exists():
            raise FileNotFoundError("FedVLR workbench runner is missing")

        normalized_payload = dict(payload)
        normalized_payload.setdefault("execution_mode", "full_train")
        response = self._validation_with_preflight(normalized_payload)
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
                "forward_preflight": response.get("forward_preflight"),
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
        shape_fields = self._shape_failure_fields(status)
        progress_detail = self._read_progress(job_dir, status)
        epoch_metrics = self._read_epoch_metrics(job_dir)
        performance_summary = self._read_json(job_dir / "performance_summary.json") if (job_dir / "performance_summary.json").exists() else None
        gpu_stats = self._read_gpu_stats(job_dir)
        return {
            "job_id": job_id,
            "status": status.get("status"),
            "stage": (progress_detail or {}).get("phase") or status.get("stage"),
            "progress": (progress_detail or {}).get("percent"),
            "progress_detail": progress_detail,
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
            "error_detail": self._safe_relative_string(str(status.get("error_detail"))) if status.get("error_detail") else None,
            "failure_stage": status.get("failure_stage"),
            "runner_pid": status.get("runner_pid"),
            "pid": status.get("pid"),
            "return_code": status.get("return_code"),
            "subprocess_command": None,
            "python_path": Path(str(status.get("python_path"))).name if status.get("python_path") else None,
            "cwd": "." if status.get("cwd") else None,
            "result_dir": status.get("result_dir"),
            "artifact_dir": status.get("artifact_dir"),
            "source": status.get("source"),
            "warnings": status.get("warnings", []),
            "errors": status.get("errors", []),
            "config_summary": config_summary,
            "forward_preflight": status.get("forward_preflight"),
            "epoch_metrics": epoch_metrics,
            "gpu_stats": gpu_stats,
            "performance_summary": performance_summary,
            **shape_fields,
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
                "error_detail": self._safe_relative_string(str(status_payload.get("error_detail"))) if status_payload.get("error_detail") else None,
                "return_code": status_payload.get("return_code"),
                "key_metrics": self._compact_metrics(metrics_summary),
                "result_dir": status_payload.get("result_dir"),
                "artifact_dir": status_payload.get("artifact_dir"),
                "forward_preflight": status_payload.get("forward_preflight"),
                **self._shape_failure_fields(status_payload),
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
            "lines": [self._safe_relative_string(line) or "" for line in lines[-bounded_tail:]],
            "has_more": len(lines) > bounded_tail,
        }

    def get_result(self, job_id: str) -> Dict[str, Any]:
        job_dir = self._safe_job_dir(job_id)
        status = self._read_json(job_dir / "status.json")
        pointer = self._read_json(job_dir / "result_pointer.json") if (job_dir / "result_pointer.json").exists() else None
        metrics = self._read_json(job_dir / "metrics_summary.json") if (job_dir / "metrics_summary.json").exists() else None
        normalized = self._normalize_result(job_id, status, metrics)
        progress_detail = self._read_progress(job_dir, status)
        return {
            "job_id": job_id,
            "status": (pointer or {}).get("status") or status.get("status"),
            "stage": status.get("stage"),
            "source": (pointer or {}).get("source") or status.get("source"),
            "result_pointer": self._sanitize_payload(pointer),
            "metrics_summary": normalized,
            "result": normalized,
            "warnings": (normalized or {}).get("warnings", status.get("warnings", [])),
            "missing_evidence": (normalized or {}).get("missing_evidence", []),
            "failure_stage": status.get("failure_stage"),
            "error_summary": status.get("error_summary") or status.get("error_message"),
            "error_detail": self._safe_relative_string(str(status.get("error_detail"))) if status.get("error_detail") else None,
            "actual_tensor_shapes": self._shape_failure_fields(status).get("actual_tensor_shapes"),
            "model_expected_shapes": self._shape_failure_fields(status).get("model_expected_shapes"),
            "progress_detail": progress_detail,
            "epoch_metrics": self._read_epoch_metrics(job_dir),
            "gpu_stats": self._read_gpu_stats(job_dir),
            "performance_summary": self._read_json(job_dir / "performance_summary.json") if (job_dir / "performance_summary.json").exists() else None,
            "message": "结果来自真实全量训练任务。",
        }


@lru_cache(maxsize=1)
def get_workbench_service() -> WorkbenchService:
    return WorkbenchService(get_settings())
