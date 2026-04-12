from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from app.core.settings import get_settings


CAPABILITY_MATRIX_PATH = Path("configs") / "model_attack_defense_capabilities.json"
EXPERIMENT_SCHEMA_PATH = Path("configs") / "experiment_config_schema.json"


class CapabilityStore:
    """Read-only wrapper around FedVLR capability and schema JSON files."""

    def __init__(self, fedvlr_root: Path) -> None:
        self.fedvlr_root = fedvlr_root

    def get_capabilities(self) -> Dict[str, Any]:
        file_path = self.fedvlr_root / CAPABILITY_MATRIX_PATH
        payload = self._read_json(file_path)
        return {
            "source": CAPABILITY_MATRIX_PATH.as_posix(),
            "updated_at": self._updated_at(file_path),
            "model_count": len(payload.get("models", [])),
            "attack_count": len(payload.get("attacks", [])),
            "defense_count": len(payload.get("defenses", [])),
            "privacy_metric_count": len(payload.get("privacy_metrics", [])),
            "validated_combination_count": len(
                payload.get("validated_combinations", [])
            ),
            "data": payload,
        }

    def get_experiment_schema(self) -> Dict[str, Any]:
        file_path = self.fedvlr_root / EXPERIMENT_SCHEMA_PATH
        payload = self._read_json(file_path)
        return {
            "source": EXPERIMENT_SCHEMA_PATH.as_posix(),
            "updated_at": self._updated_at(file_path),
            "required_fields": list(payload.get("required", [])),
            "data": payload,
        }

    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        try:
            with open(file_path, "r", encoding="utf-8-sig") as file:
                data = json.load(file)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"FedVLR config file not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON file: {file_path}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object in file: {file_path}")
        return data

    def _updated_at(self, file_path: Path) -> str:
        return datetime.fromtimestamp(
            file_path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()


@lru_cache(maxsize=1)
def get_capability_store() -> CapabilityStore:
    settings = get_settings()
    return CapabilityStore(settings.fedvlr_root)
