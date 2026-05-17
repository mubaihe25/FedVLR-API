from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from app.core.settings import get_settings


@dataclass(frozen=True)
class ArtifactSpec:
    key: str
    response_key: str
    file_name: str


@dataclass(frozen=True)
class ArtifactReadResult:
    data: Any | None
    warnings: List[Dict[str, str]]
    missing: bool = False


ARTIFACT_SPECS: Dict[str, ArtifactSpec] = {
    "manifest": ArtifactSpec(
        key="manifest",
        response_key="manifest",
        file_name="showcase_manifest.json",
    ),
    "dataset_profile": ArtifactSpec(
        key="dataset_profile",
        response_key="dataset_profile",
        file_name="dataset_profile.json",
    ),
    "metrics_summary": ArtifactSpec(
        key="metrics_summary",
        response_key="metrics_summary",
        file_name="metrics_summary.json",
    ),
    "attack_defense_summary": ArtifactSpec(
        key="attack_defense_summary",
        response_key="attack_defense_summary",
        file_name="attack_defense_summary.json",
    ),
    "recommendation_comparison": ArtifactSpec(
        key="recommendation_comparison",
        response_key="recommendation_comparison",
        file_name="recommendation_comparison.json",
    ),
    "defense_trace": ArtifactSpec(
        key="defense_trace",
        response_key="defense_trace",
        file_name="defense_trace.json",
    ),
    "privacy_risk_summary": ArtifactSpec(
        key="privacy_risk_summary",
        response_key="privacy_risk_summary",
        file_name="privacy_risk_summary.json",
    ),
}

EXPECTED_ARTIFACT_FILES = tuple(spec.file_name for spec in ARTIFACT_SPECS.values())
REPORT_ARTIFACT_KEYS = (
    "manifest",
    "dataset_profile",
    "metrics_summary",
    "attack_defense_summary",
    "recommendation_comparison",
    "defense_trace",
    "privacy_risk_summary",
)
SECURITY_ARTIFACT_KEYS = ("attack_defense_summary", "defense_trace")

FRIENDLY_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "mmfedrap_ku_main_showcase": {
        "name": "KU 多模态联邦推荐攻防主结果",
        "tags": ["KU", "MMFedRAP", "AttackDefense"],
    },
    "mmfedrap_ku_attack_defense_demo": {
        "name": "KU 多模态联邦推荐攻防主结果",
        "tags": ["KU", "MMFedRAP", "AttackDefense"],
    },
    "amazon_beauty_poc_security_smoke": {
        "name": "Amazon Beauty 商品推荐安全分析",
        "tags": ["Amazon", "Product", "SecuritySmoke"],
    },
    "amazon_beauty_poc_target_injection_strong_smoke": {
        "name": "Amazon Beauty 目标注入排序推进",
        "tags": ["Amazon", "TargetInjection", "RankShift"],
    },
    "amazon_beauty_poc_target_rank_comparison_smoke": {
        "name": "Amazon Beauty 目标排序对照",
        "tags": ["Amazon", "TargetRank"],
    },
    "security_matrix_krum_demo": {
        "name": "鲁棒聚合 Krum 链路验证",
        "tags": ["RobustAggregation", "Krum"],
    },
}


class ShowcaseArtifactStore:
    """Read-only wrapper around exported FedVLR showcase artifacts."""

    def __init__(self, fedvlr_root: Path, artifact_root: Path) -> None:
        self.fedvlr_root = fedvlr_root.resolve()
        self.artifact_root = artifact_root.resolve()

    def list_scenarios(self) -> Dict[str, Any]:
        warnings = self._root_warnings()
        if warnings:
            return {"count": 0, "items": [], "warnings": warnings}

        items = [self._build_scenario_item(path) for path in self._scenario_dirs()]
        return {"count": len(items), "items": items, "warnings": []}

    def load_artifact(self, scenario_id: str, artifact_key: str) -> Dict[str, Any]:
        spec = self._get_artifact_spec(artifact_key)
        scenario_dir = self._get_scenario_dir(scenario_id)
        result = self._read_artifact(scenario_dir, spec)
        if result.missing:
            raise FileNotFoundError(
                f"{spec.file_name} not found for showcase scenario '{scenario_id}'"
            )
        return {
            "scenario_id": scenario_id,
            "artifact": spec.response_key,
            "file": spec.file_name,
            "data": result.data,
            "warnings": result.warnings,
        }

    def load_security(self, scenario_id: str) -> Dict[str, Any]:
        return self._load_artifact_group(scenario_id, SECURITY_ARTIFACT_KEYS)

    def load_report(self, scenario_id: str) -> Dict[str, Any]:
        return self._load_artifact_group(scenario_id, REPORT_ARTIFACT_KEYS)

    def _load_artifact_group(
        self,
        scenario_id: str,
        artifact_keys: Sequence[str],
    ) -> Dict[str, Any]:
        scenario_dir = self._get_scenario_dir(scenario_id)
        response: Dict[str, Any] = {"scenario_id": scenario_id, "warnings": []}

        for artifact_key in artifact_keys:
            spec = self._get_artifact_spec(artifact_key)
            result = self._read_artifact(scenario_dir, spec)
            response[spec.response_key] = result.data
            response["warnings"].extend(result.warnings)

        return response

    def _build_scenario_item(self, scenario_dir: Path) -> Dict[str, Any]:
        scenario_id = scenario_dir.name
        scenario_warnings: List[Dict[str, str]] = []
        manifest = self._read_metadata_artifact(
            scenario_dir,
            ARTIFACT_SPECS["manifest"],
            scenario_warnings,
        )
        dataset_profile = self._read_metadata_artifact(
            scenario_dir,
            ARTIFACT_SPECS["dataset_profile"],
            scenario_warnings,
        )

        missing_files = [
            file_name
            for file_name in EXPECTED_ARTIFACT_FILES
            if not (scenario_dir / file_name).is_file()
        ]
        for file_name in missing_files:
            scenario_warnings.append(
                self._warning(
                    "missing_artifact",
                    f"{file_name} is not available for this scenario.",
                    file_name,
                )
            )

        friendly = FRIENDLY_SCENARIOS.get(scenario_id, {})
        name = self._first_string(
            friendly.get("name"),
            self._lookup_value(manifest, ("name", "title", "scenario_name")),
            self._humanize_scenario_id(scenario_id),
        )
        tags = self._coerce_string_list(friendly.get("tags"))
        if not tags:
            tags = self._first_string_list(
                self._lookup_value(manifest, ("tags", "scenario_tags")),
                self._lookup_value(dataset_profile, ("tags", "scenario_tags")),
            )

        return {
            "id": scenario_id,
            "name": name,
            "path": self._public_scenario_path(scenario_dir),
            "available_files": self._available_files(scenario_dir),
            "dataset": self._first_string(
                self._lookup_value(
                    manifest,
                    ("dataset", "dataset_name", "dataset_id"),
                ),
                self._lookup_value(
                    dataset_profile,
                    ("dataset", "dataset_name", "dataset_id"),
                ),
            ),
            "model": self._first_string(
                self._lookup_value(manifest, ("model", "model_name", "base_model")),
                self._lookup_value(
                    dataset_profile,
                    ("model", "model_name", "base_model"),
                ),
            ),
            "description": self._first_string(
                self._lookup_value(manifest, ("description", "summary")),
                self._lookup_value(dataset_profile, ("description", "summary")),
            ),
            "tags": tags,
            "warnings": scenario_warnings,
        }

    def _read_metadata_artifact(
        self,
        scenario_dir: Path,
        spec: ArtifactSpec,
        warnings: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        result = self._read_artifact(scenario_dir, spec)
        warnings.extend(
            warning
            for warning in result.warnings
            if warning.get("code") != "missing_artifact"
        )
        if result.missing or result.warnings:
            return {}
        if isinstance(result.data, dict):
            return result.data
        warnings.append(
            self._warning(
                "unexpected_json_type",
                f"{spec.file_name} is valid JSON but is not an object.",
                spec.file_name,
            )
        )
        return {}

    def _read_artifact(
        self,
        scenario_dir: Path,
        spec: ArtifactSpec,
    ) -> ArtifactReadResult:
        file_path = scenario_dir / spec.file_name
        if not file_path.is_file():
            return ArtifactReadResult(
                data=None,
                missing=True,
                warnings=[
                    self._warning(
                        "missing_artifact",
                        f"{spec.file_name} is not available for this scenario.",
                        spec.file_name,
                    )
                ],
            )

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return ArtifactReadResult(data=json.load(file), warnings=[])
        except json.JSONDecodeError as exc:
            return ArtifactReadResult(
                data=None,
                warnings=[
                    self._warning(
                        "invalid_json",
                        (
                            f"{spec.file_name} is not valid JSON: {exc.msg} "
                            f"at line {exc.lineno}, column {exc.colno}."
                        ),
                        spec.file_name,
                    )
                ],
            )

    def _get_artifact_spec(self, artifact_key: str) -> ArtifactSpec:
        try:
            return ARTIFACT_SPECS[artifact_key]
        except KeyError as exc:
            raise ValueError(f"Unknown showcase artifact key: {artifact_key}") from exc

    def _root_warnings(self) -> List[Dict[str, str]]:
        if not self.artifact_root.exists():
            return [
                self._warning(
                    "artifact_root_missing",
                    "Showcase artifact root is not available.",
                    None,
                )
            ]
        if not self.artifact_root.is_dir():
            return [
                self._warning(
                    "artifact_root_not_directory",
                    "Showcase artifact root is not a directory.",
                    None,
                )
            ]
        return []

    def _scenario_dirs(self) -> List[Path]:
        scenario_dirs = []
        for path in self.artifact_root.iterdir():
            if not path.is_dir():
                continue
            resolved_path = path.resolve()
            if self._is_within_artifact_root(resolved_path):
                scenario_dirs.append(resolved_path)
        return sorted(scenario_dirs, key=lambda path: path.name.lower())

    def _get_scenario_dir(self, scenario_id: str) -> Path:
        if not scenario_id or Path(scenario_id).name != scenario_id:
            raise FileNotFoundError(f"Showcase scenario not found: {scenario_id}")

        if self._root_warnings():
            raise FileNotFoundError(f"Showcase scenario not found: {scenario_id}")

        scenario_dir = (self.artifact_root / scenario_id).resolve()
        if (
            not self._is_within_artifact_root(scenario_dir)
            or not scenario_dir.is_dir()
        ):
            raise FileNotFoundError(f"Showcase scenario not found: {scenario_id}")
        return scenario_dir

    def _is_within_artifact_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.artifact_root)
        except ValueError:
            return False
        return True

    def _public_scenario_path(self, scenario_dir: Path) -> str:
        try:
            return scenario_dir.relative_to(self.fedvlr_root).as_posix()
        except ValueError:
            return scenario_dir.relative_to(self.artifact_root).as_posix()

    def _available_files(self, scenario_dir: Path) -> List[str]:
        return sorted(path.name for path in scenario_dir.iterdir() if path.is_file())

    def _lookup_value(self, payload: Dict[str, Any], keys: Iterable[str]) -> Any:
        for key in keys:
            if key in payload:
                return payload[key]

        for container_key in ("metadata", "profile", "experiment", "config"):
            nested = payload.get(container_key)
            if not isinstance(nested, dict):
                continue
            for key in keys:
                if key in nested:
                    return nested[key]

        return None

    def _first_string(self, *values: Any) -> str | None:
        for value in values:
            string_value = self._coerce_string(value)
            if string_value:
                return string_value
        return None

    def _coerce_string(self, value: Any) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            for key in ("name", "title", "id", "label"):
                string_value = self._coerce_string(value.get(key))
                if string_value:
                    return string_value
        return None

    def _first_string_list(self, *values: Any) -> List[str]:
        for value in values:
            string_list = self._coerce_string_list(value)
            if string_list:
                return string_list
        return []

    def _coerce_string_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [
                string_value
                for item in value
                if (string_value := self._coerce_string(item))
            ]
        string_value = self._coerce_string(value)
        return [string_value] if string_value else []

    def _humanize_scenario_id(self, scenario_id: str) -> str:
        return " ".join(part for part in scenario_id.replace("-", "_").split("_") if part)

    def _warning(
        self,
        code: str,
        message: str,
        file_name: str | None,
    ) -> Dict[str, str]:
        warning = {"code": code, "message": message}
        if file_name:
            warning["file"] = file_name
        return warning


@lru_cache(maxsize=1)
def get_showcase_store() -> ShowcaseArtifactStore:
    settings = get_settings()
    return ShowcaseArtifactStore(
        fedvlr_root=settings.fedvlr_root,
        artifact_root=settings.showcase_artifact_root,
    )
