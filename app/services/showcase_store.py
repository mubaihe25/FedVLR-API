from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence
from urllib.parse import quote

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
    "model_security_capability_matrix": ArtifactSpec(
        key="model_security_capability_matrix",
        response_key="model_security_capability_matrix",
        file_name="model_security_capability_matrix.json",
    ),
    "supported_demos": ArtifactSpec(
        key="supported_demos",
        response_key="supported_demos",
        file_name="supported_demos.json",
    ),
    "unsupported_reasons": ArtifactSpec(
        key="unsupported_reasons",
        response_key="unsupported_reasons",
        file_name="unsupported_reasons.json",
    ),
    "recommended_frontend_labels": ArtifactSpec(
        key="recommended_frontend_labels",
        response_key="recommended_frontend_labels",
        file_name="recommended_frontend_labels.json",
    ),
}

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
MATRIX_ARTIFACT_KEYS = (
    "model_security_capability_matrix",
    "supported_demos",
    "unsupported_reasons",
    "recommended_frontend_labels",
)
STANDARD_EXPECTED_ARTIFACT_FILES = tuple(
    ARTIFACT_SPECS[key].file_name for key in REPORT_ARTIFACT_KEYS
)
MATRIX_EXPECTED_ARTIFACT_FILES = (
    ARTIFACT_SPECS["manifest"].file_name,
    *(ARTIFACT_SPECS[key].file_name for key in MATRIX_ARTIFACT_KEYS),
)

FRIENDLY_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "mmfedrap_ku_main_showcase": {
        "name": "KU MMFedRAP attack-defense main result",
        "tags": ["KU", "MMFedRAP", "AttackDefense"],
    },
    "mmfedrap_ku_attack_defense_demo": {
        "name": "KU MMFedRAP attack-defense main result",
        "tags": ["KU", "MMFedRAP", "AttackDefense"],
    },
    "amazon_beauty_poc_security_smoke": {
        "name": "Amazon Beauty product security smoke",
        "tags": ["Amazon", "Product", "SecuritySmoke"],
    },
    "amazon_beauty_poc_target_injection_strong_smoke": {
        "name": "Amazon Beauty target injection rank shift",
        "tags": ["Amazon", "TargetInjection", "RankShift"],
    },
    "amazon_beauty_poc_target_rank_comparison_smoke": {
        "name": "Amazon Beauty target rank comparison",
        "tags": ["Amazon", "TargetRank"],
    },
    "amazon_beauty_poc_v25_backend_smoke": {
        "name": "Amazon Beauty V2.5 backend smoke",
        "dataset": "AMAZON_BEAUTY_POC",
        "model": "FedAvg",
        "tags": ["Amazon", "V2.5", "TargetRank", "PrivacySmoke"],
    },
    "security_matrix_krum_demo": {
        "name": "Robust aggregation Krum chain",
        "tags": ["RobustAggregation", "Krum"],
    },
    "model_security_capability_matrix": {
        "name": "模型安全能力矩阵",
        "dataset": "AMAZON_BEAUTY_POC / KU",
        "model": "FedAvg / MMFedRAP / FedRAP / MMFedAvg",
        "tags": ["ModelMatrix", "SecurityCapability", "FrontendLabels"],
    },
}


class ShowcaseArtifactStore:
    """Read-only wrapper around exported FedVLR showcase artifacts."""

    def __init__(
        self,
        fedvlr_root: Path,
        artifact_root: Path,
        amazon_beauty_image_manifest: Path,
    ) -> None:
        self.fedvlr_root = fedvlr_root.resolve()
        self.artifact_root = artifact_root.resolve()
        self.amazon_beauty_image_manifest = amazon_beauty_image_manifest.resolve()
        self._image_manifest_cache: Dict[str, Any] | None = None

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
        scenario_dir = self._get_scenario_dir(scenario_id)
        artifact_keys = REPORT_ARTIFACT_KEYS
        if self._is_matrix_scenario(scenario_dir):
            artifact_keys = ("manifest", *MATRIX_ARTIFACT_KEYS)
        return self._load_artifact_group_from_dir(
            scenario_id,
            scenario_dir,
            artifact_keys,
        )

    def get_image_path(self, dataset: str, item_id: str) -> Path | None:
        if not self._is_safe_path_segment(dataset):
            return None
        if not self._is_safe_path_segment(item_id):
            return None

        manifest = self._load_image_manifest()
        if dataset != manifest.get("dataset"):
            return None

        image_path = manifest.get("items", {}).get(item_id)
        if not isinstance(image_path, Path) or not image_path.is_file():
            return None
        return image_path

    def _load_artifact_group(
        self,
        scenario_id: str,
        artifact_keys: Sequence[str],
    ) -> Dict[str, Any]:
        scenario_dir = self._get_scenario_dir(scenario_id)
        return self._load_artifact_group_from_dir(
            scenario_id,
            scenario_dir,
            artifact_keys,
        )

    def _load_artifact_group_from_dir(
        self,
        scenario_id: str,
        scenario_dir: Path,
        artifact_keys: Sequence[str],
    ) -> Dict[str, Any]:
        response: Dict[str, Any] = {"scenario_id": scenario_id, "warnings": []}

        for artifact_key in artifact_keys:
            spec = self._get_artifact_spec(artifact_key)
            result = self._read_artifact(
                scenario_dir,
                spec,
                preview=artifact_key == "recommendation_comparison",
            )
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
            for file_name in self._expected_artifact_files(scenario_dir)
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
                friendly.get("dataset"),
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
                friendly.get("model"),
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
        preview: bool = False,
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
                data = json.load(file)
                if preview and spec.key == "recommendation_comparison":
                    data = self._preview_recommendation_payload(data)
                return ArtifactReadResult(
                    data=self._publicize_payload(data, scenario_dir),
                    warnings=[],
                )
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

    def _expected_artifact_files(self, scenario_dir: Path) -> Sequence[str]:
        if self._is_matrix_scenario(scenario_dir):
            return MATRIX_EXPECTED_ARTIFACT_FILES
        return STANDARD_EXPECTED_ARTIFACT_FILES

    def _is_matrix_scenario(self, scenario_dir: Path) -> bool:
        return (
            scenario_dir / ARTIFACT_SPECS["model_security_capability_matrix"].file_name
        ).is_file()

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

    def _preview_recommendation_payload(self, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        preview_limit = 100
        preview_data = dict(data)
        total_counts: Dict[str, int] = {}
        truncated_keys: List[str] = []
        recommendation_keys = {
            "baseline",
            "attack",
            "attacked",
            "defense",
            "baseline_recommendations",
            "attack_recommendations",
            "attacked_recommendations",
            "defense_recommendations",
            "defended_recommendations",
        }

        for key, value in data.items():
            if not isinstance(value, list):
                continue
            if key not in recommendation_keys and not key.endswith("_recommendations"):
                continue

            total_counts[key] = len(value)
            if len(value) > preview_limit:
                preview_data[key] = value[:preview_limit]
                truncated_keys.append(key)

        if truncated_keys:
            preview_data["preview_limit"] = preview_limit
            preview_data["total_counts"] = {
                **(data.get("total_counts") if isinstance(data.get("total_counts"), dict) else {}),
                **total_counts,
            }
            warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
            preview_data["warnings"] = [
                *warnings,
                (
                    "recommendation_comparison is preview-limited in /report; "
                    "use /showcase/scenarios/{scenario_id}/recommendations for the full artifact."
                ),
            ]

        return preview_data

    def _load_image_manifest(self) -> Dict[str, Any]:
        if self._image_manifest_cache is not None:
            return self._image_manifest_cache

        empty_manifest: Dict[str, Any] = {"dataset": None, "items": {}}
        if not self.amazon_beauty_image_manifest.is_file():
            self._image_manifest_cache = empty_manifest
            return self._image_manifest_cache

        try:
            with open(self.amazon_beauty_image_manifest, "r", encoding="utf-8") as file:
                manifest = json.load(file)
        except (OSError, json.JSONDecodeError):
            self._image_manifest_cache = empty_manifest
            return self._image_manifest_cache

        if not isinstance(manifest, dict):
            self._image_manifest_cache = empty_manifest
            return self._image_manifest_cache

        dataset = self._coerce_string(manifest.get("dataset")) or "AMAZON_BEAUTY_POC"
        output_dir = self._coerce_string(manifest.get("output_dir"))
        image_root = (
            self._resolve_fedvlr_path(output_dir)
            if output_dir
            else self.amazon_beauty_image_manifest.parent
        )
        items: Dict[str, Path] = {}

        for item in manifest.get("items", []):
            if not isinstance(item, dict):
                continue
            local_image_path = self._coerce_string(item.get("local_image_path"))
            if not local_image_path:
                continue
            image_path = self._resolve_fedvlr_path(local_image_path)
            if not self._is_within_path(image_path, image_root):
                continue

            item_ids = [
                self._coerce_string(item.get("itemID")),
                self._coerce_string(item.get("item_id")),
                self._coerce_string(item.get("id")),
                self._coerce_string(item.get("raw_item_id")),
            ]
            for item_id in item_ids:
                if item_id and self._is_safe_path_segment(item_id):
                    items[item_id] = image_path

        self._image_manifest_cache = {"dataset": dataset, "items": items}
        return self._image_manifest_cache

    def _publicize_payload(self, value: Any, scenario_dir: Path) -> Any:
        return self._publicize_value(value, self._infer_dataset(scenario_dir))

    def _publicize_value(self, value: Any, dataset: str | None) -> Any:
        if isinstance(value, dict):
            public_value = {
                key: self._publicize_value(item, dataset)
                for key, item in value.items()
            }
            item_id = self._first_string(
                public_value.get("item_id"),
                public_value.get("itemID"),
                public_value.get("itemId"),
                public_value.get("id"),
                public_value.get("asin"),
                public_value.get("raw_item_id"),
            )
            if (
                dataset
                and item_id
                and "local_image_url" not in public_value
                and self.get_image_path(dataset, item_id)
            ):
                public_value["local_image_url"] = (
                    f"/showcase/images/{dataset}/{quote(item_id, safe='')}"
                )
            return public_value

        if isinstance(value, list):
            return [self._publicize_value(item, dataset) for item in value]

        if isinstance(value, str):
            return self._publicize_string(value)

        return value

    def _publicize_string(self, value: str) -> str:
        if "://" in value:
            return value
        if "\\" not in value and "/" not in value:
            return value

        path = Path(value)
        if path.is_absolute():
            resolved_path = path.resolve()
            if self._is_within_path(resolved_path, self.fedvlr_root):
                return resolved_path.relative_to(self.fedvlr_root).as_posix()
            return path.name

        return value.replace("\\", "/")

    def _infer_dataset(self, scenario_dir: Path) -> str | None:
        scenario_id = scenario_dir.name.lower()
        if "amazon_beauty" in scenario_id:
            return "AMAZON_BEAUTY_POC"
        return None

    def _resolve_fedvlr_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (self.fedvlr_root / path).resolve()

    def _is_within_path(self, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True

    def _is_safe_path_segment(self, value: str) -> bool:
        if not value or value in {".", ".."}:
            return False
        path = Path(value)
        if path.name != value:
            return False
        return "/" not in value and "\\" not in value and ".." not in value

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
        amazon_beauty_image_manifest=settings.amazon_beauty_image_manifest,
    )
