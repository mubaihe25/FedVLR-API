from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import get_settings


SUMMARY_SUFFIX = ".experiment_summary.json"
RESULT_SUFFIX = ".experiment_result.json"


@dataclass
class ExperimentFileRecord:
    experiment_key: str
    file_name: str
    relative_path: str
    sort_timestamp: float
    summary_path: Optional[Path] = None
    result_path: Optional[Path] = None


class ExperimentResultStore:
    """Read-only wrapper around FedVLR experiment JSON outputs."""

    def __init__(self, results_dir: Path) -> None:
        self.results_dir = results_dir

    def list_summaries(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for record in self._scan_index():
            if not record.summary_path:
                continue
            payload = self._read_json(record.summary_path)
            items.append(self._build_summary_list_item(record, payload))
        return items

    def get_summary(self, experiment_key: str) -> Dict[str, Any]:
        record = self._get_record(experiment_key)
        if not record.summary_path:
            raise FileNotFoundError(
                f"Summary file not found for experiment_key='{experiment_key}'"
            )
        return {
            "experiment_key": record.experiment_key,
            "file_name": record.file_name,
            "relative_path": record.relative_path,
            "summary": self._read_json(record.summary_path),
        }

    def get_result(self, experiment_key: str) -> Dict[str, Any]:
        record = self._get_record(experiment_key)
        if not record.result_path:
            raise FileNotFoundError(
                f"Result file not found for experiment_key='{experiment_key}'"
            )
        return {
            "experiment_key": record.experiment_key,
            "file_name": record.file_name,
            "relative_path": record.relative_path,
            "result": self._read_json(record.result_path),
        }

    def _get_record(self, experiment_key: str) -> ExperimentFileRecord:
        for record in self._scan_index():
            if record.experiment_key == experiment_key:
                return record
        raise FileNotFoundError(f"Experiment '{experiment_key}' not found")

    def _scan_index(self) -> List[ExperimentFileRecord]:
        if not self.results_dir.exists():
            return []

        records: Dict[str, ExperimentFileRecord] = {}
        for file_path in self.results_dir.rglob("*.json"):
            suffix = self._match_suffix(file_path.name)
            if not suffix:
                continue

            relative_path = file_path.relative_to(self.results_dir)
            relative_base = self._strip_known_suffix(relative_path)
            experiment_key = self._build_experiment_key(relative_base)
            file_name = file_path.name
            sort_timestamp = file_path.stat().st_mtime

            record = records.get(experiment_key)
            if record is None:
                record = ExperimentFileRecord(
                    experiment_key=experiment_key,
                    file_name=file_name,
                    relative_path=relative_base.as_posix(),
                    sort_timestamp=sort_timestamp,
                )
                records[experiment_key] = record
            else:
                record.sort_timestamp = max(record.sort_timestamp, sort_timestamp)

            if suffix == SUMMARY_SUFFIX:
                record.summary_path = file_path
            elif suffix == RESULT_SUFFIX:
                record.result_path = file_path

        return sorted(
            records.values(),
            key=lambda item: (item.sort_timestamp, item.relative_path),
            reverse=True,
        )

    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Result file not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON file: {file_path}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object in file: {file_path}")
        return data

    def _match_suffix(self, file_name: str) -> Optional[str]:
        if file_name.endswith(SUMMARY_SUFFIX):
            return SUMMARY_SUFFIX
        if file_name.endswith(RESULT_SUFFIX):
            return RESULT_SUFFIX
        return None

    def _strip_known_suffix(self, relative_path: Path) -> Path:
        relative_str = relative_path.as_posix()
        for suffix in (SUMMARY_SUFFIX, RESULT_SUFFIX):
            if relative_str.endswith(suffix):
                return Path(relative_str[: -len(suffix)])
        return relative_path

    def _build_experiment_key(self, relative_base: Path) -> str:
        return "__".join(relative_base.parts)

    def _build_summary_list_item(
        self,
        record: ExperimentFileRecord,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "experiment_key": record.experiment_key,
            "file_name": record.file_name,
            "relative_path": record.relative_path,
            "experiment_id": payload.get("experiment_id"),
            "model": payload.get("model"),
            "dataset": payload.get("dataset"),
            "experiment_mode": payload.get("experiment_mode"),
            "scenario_tags": list(payload.get("scenario_tags", [])),
            "active_attacks": list(payload.get("active_attacks", [])),
            "active_defenses": list(payload.get("active_defenses", [])),
            "active_privacy_metrics": list(
                payload.get("active_privacy_metrics", [])
            ),
            "final_eval": payload.get("final_eval", {}) or {},
        }


@lru_cache(maxsize=1)
def get_result_store() -> ExperimentResultStore:
    settings = get_settings()
    return ExperimentResultStore(settings.results_dir)
