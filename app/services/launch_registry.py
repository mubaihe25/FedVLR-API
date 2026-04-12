from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LaunchRegistry:
    """In-memory launch status registry for the minimal async API layer.

    This registry is intentionally process-local. It gives the frontend a
    lightweight polling target without introducing a database or task queue.
    """

    def __init__(self) -> None:
        self._records: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(
        self,
        launch_id: str,
        launch_mode: str,
        command: List[str],
        config_summary: Dict[str, Any],
        validate_only: bool,
        dry_run: bool,
        strict_validation: bool,
        status: str = "queued",
    ) -> Dict[str, Any]:
        now = utc_now()
        record = {
            "launch_id": launch_id,
            "accepted": True,
            "success": status not in {"failed"},
            "status": status,
            "launch_mode": launch_mode,
            "submitted_at": now,
            "started_at": None,
            "finished_at": None,
            "pid": None,
            "command": command,
            "return_code": None,
            "experiment_id": None,
            "result_dir": None,
            "summary_path": None,
            "result_path": None,
            "csv_path": None,
            "validation_warnings": [],
            "errors": [],
            "stdout_tail": "",
            "stderr_tail": "",
            "launcher_payload": {},
            "config_summary": config_summary,
            "validate_only": validate_only,
            "dry_run": dry_run,
            "strict_validation": strict_validation,
        }
        with self._lock:
            self._records[launch_id] = record
            return deepcopy(record)

    def update(self, launch_id: str, **updates: Any) -> Dict[str, Any] | None:
        with self._lock:
            record = self._records.get(launch_id)
            if record is None:
                return None
            record.update(updates)
            return deepcopy(record)

    def get(self, launch_id: str) -> Dict[str, Any] | None:
        with self._lock:
            record = self._records.get(launch_id)
            return deepcopy(record) if record is not None else None


@lru_cache(maxsize=1)
def get_launch_registry() -> LaunchRegistry:
    return LaunchRegistry()
