from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple
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
    "v3_profile": ArtifactSpec(
        key="v3_profile",
        response_key="profile",
        file_name="scenario_profile.json",
    ),
    "v3_runtime": ArtifactSpec(
        key="v3_runtime",
        response_key="runtime",
        file_name="runtime_timeline.json",
    ),
    "v3_curves": ArtifactSpec(
        key="v3_curves",
        response_key="curves",
        file_name="training_curves.json",
    ),
    "v3_target_manipulation": ArtifactSpec(
        key="v3_target_manipulation",
        response_key="target_manipulation",
        file_name="target_manipulation_metrics.json",
    ),
    "v3_membership": ArtifactSpec(
        key="v3_membership",
        response_key="membership",
        file_name="membership_inference_panel.json",
    ),
    "v3_update_leakage": ArtifactSpec(
        key="v3_update_leakage",
        response_key="update_leakage",
        file_name="update_leakage_panel.json",
    ),
    "v3_aggregation_defense": ArtifactSpec(
        key="v3_aggregation_defense",
        response_key="aggregation_defense",
        file_name="aggregation_defense_panel.json",
    ),
    "v3_privacy_defense": ArtifactSpec(
        key="v3_privacy_defense",
        response_key="privacy_defense",
        file_name="privacy_defense_panel.json",
    ),
    "v3_model_support": ArtifactSpec(
        key="v3_model_support",
        response_key="model_support",
        file_name="model_support_panel.json",
    ),
    "v3_frontend_summary": ArtifactSpec(
        key="v3_frontend_summary",
        response_key="frontend_summary",
        file_name="frontend_summary.json",
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
V3_ARTIFACT_KEYS = (
    "v3_profile",
    "v3_runtime",
    "v3_curves",
    "v3_target_manipulation",
    "v3_membership",
    "v3_update_leakage",
    "v3_aggregation_defense",
    "v3_privacy_defense",
    "v3_model_support",
    "v3_frontend_summary",
)
V3_EXPECTED_ARTIFACT_FILES = tuple(
    ARTIFACT_SPECS[key].file_name for key in V3_ARTIFACT_KEYS
)
V3_ROUTE_PANEL_KEYS: Dict[str, str] = {
    "profile": "v3_profile",
    "runtime": "v3_runtime",
    "curves": "v3_curves",
    "target-manipulation": "v3_target_manipulation",
    "membership": "v3_membership",
    "update-leakage": "v3_update_leakage",
    "aggregation-defense": "v3_aggregation_defense",
    "privacy-defense": "v3_privacy_defense",
    "model-support": "v3_model_support",
    "frontend-summary": "v3_frontend_summary",
}
V3_DIRECTION_PANEL_KEYS: Dict[str, str] = {
    "recommendation_manipulation": "v3_target_manipulation",
    "membership_inference": "v3_membership",
    "update_leakage": "v3_update_leakage",
    "aggregation_defense": "v3_aggregation_defense",
}

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
    "amazon_beauty_poc_security_v3": {
        "name": "Amazon Beauty 安全实验 V3",
        "dataset": "AMAZON_BEAUTY_POC",
        "model": "FedAvg",
        "tags": ["Amazon", "SecurityArtifactV3", "FrontendPanels"],
    },
}

RECOMMENDATION_COLUMNS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "baseline": ("baseline_recommendations", ("baseline_recommendations", "baseline")),
    "attack": (
        "attack_recommendations",
        ("attack_recommendations", "attacked_recommendations", "attack", "attacked"),
    ),
    "defense": (
        "defended_recommendations",
        (
            "defended_recommendations",
            "defense_recommendations",
            "defense",
            "defended",
        ),
    ),
}

STATUS_DISPLAY_LABELS = {
    "available": "可用",
    "partial": "部分可用",
    "configured_only": "仅配置验证",
    "demo_only": "演示/模拟",
    "simulation": "模拟",
    "supported": "支持",
    "unsupported": "不支持",
    "future_adapter": "后续适配",
}

DIRECTION_DISPLAY_LABELS = {
    "recommendation_manipulation": "推荐操纵",
    "membership_inference": "成员推断",
    "update_leakage": "更新泄露",
    "aggregation_defense": "聚合防御",
}

V3_PANEL_DISPLAY_TAGS = {
    "v3_profile": ["场景档案"],
    "v3_runtime": ["运行时间线"],
    "v3_curves": ["训练曲线"],
    "v3_target_manipulation": ["推荐操纵", "目标排序"],
    "v3_membership": ["成员推断"],
    "v3_update_leakage": ["更新泄露"],
    "v3_aggregation_defense": ["聚合防御"],
    "v3_privacy_defense": ["隐私防御"],
    "v3_model_support": ["模型支持"],
    "v3_frontend_summary": ["前端摘要"],
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
        self._json_cache: Dict[Path, Tuple[float, Any]] = {}

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

    def load_recommendations(
        self,
        scenario_id: str,
        limit: int = 5,
        column: str = "all",
    ) -> Dict[str, Any]:
        spec = self._get_artifact_spec("recommendation_comparison")
        scenario_dir = self._get_scenario_dir(scenario_id)
        file_path = scenario_dir / spec.file_name
        if not file_path.is_file():
            raise FileNotFoundError(
                f"{spec.file_name} not found for showcase scenario '{scenario_id}'"
            )

        data = self._read_json_file(file_path)
        payload = self._build_recommendation_payload(
            data,
            scenario_dir,
            limit=limit,
            column=column,
        )
        return {
            "scenario_id": scenario_id,
            "artifact": spec.response_key,
            "file": spec.file_name,
            "data": payload,
            "warnings": [],
        }

    def load_v3_panel(self, scenario_id: str, route_panel_key: str) -> Dict[str, Any]:
        artifact_key = self._get_v3_artifact_key(route_panel_key)
        spec = self._get_artifact_spec(artifact_key)
        scenario_dir = self._get_scenario_dir(scenario_id)
        result = self._read_artifact(scenario_dir, spec)
        if result.missing:
            raise FileNotFoundError(
                f"{spec.file_name} not found for showcase V3 scenario '{scenario_id}'"
            )
        return {
            "scenario_id": scenario_id,
            "artifact": spec.response_key,
            "file": spec.file_name,
            "data": result.data,
            "warnings": result.warnings,
        }

    def load_v3_report(self, scenario_id: str) -> Dict[str, Any]:
        scenario_dir = self._get_scenario_dir(scenario_id)
        return self._load_artifact_group_from_dir(
            scenario_id,
            scenario_dir,
            V3_ARTIFACT_KEYS,
        )

    def get_image_path(
        self,
        dataset: str,
        item_id: str,
        size: str = "thumb",
    ) -> Path | None:
        if not self._is_safe_path_segment(dataset):
            return None
        if not self._is_safe_path_segment(item_id):
            return None

        manifest = self._load_image_manifest()
        if dataset != manifest.get("dataset"):
            return None

        image_info = manifest.get("items", {}).get(item_id)
        if not isinstance(image_info, dict):
            return None

        key = "thumbnail_path" if size == "thumb" else "full_path"
        image_path = image_info.get(key)
        if not isinstance(image_path, Path) or not image_path.is_file():
            if size == "thumb":
                image_path = image_info.get("full_path")
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
        is_v3 = self._is_v3_scenario(scenario_dir)
        if is_v3:
            manifest = self._read_metadata_artifact(
                scenario_dir,
                ARTIFACT_SPECS["v3_profile"],
                scenario_warnings,
            )
            dataset_profile: Dict[str, Any] = {}
            frontend_summary = self._read_metadata_artifact(
                scenario_dir,
                ARTIFACT_SPECS["v3_frontend_summary"],
                scenario_warnings,
            )
        else:
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
            frontend_summary = {}

        missing_files = [
            file_name
            for file_name in self._expected_artifact_files(scenario_dir)
            if not (scenario_dir / file_name).is_file()
        ]
        for file_name in missing_files:
            missing_code = "missing_panel" if is_v3 else "missing_artifact"
            scenario_warnings.append(
                self._warning(
                    missing_code,
                    f"{file_name} is not available for this scenario.",
                    file_name,
                )
            )

        friendly = FRIENDLY_SCENARIOS.get(scenario_id, {})
        available_files = self._available_files(scenario_dir)
        available_panels = self._available_v3_panels(scenario_dir)
        supported_directions = self._supported_v3_directions(
            scenario_dir,
            manifest,
            frontend_summary,
        )
        name = self._first_string(
            friendly.get("name"),
            self._lookup_value(manifest, ("display_name",)),
            self._lookup_value(manifest, ("name", "title", "scenario_name")),
            self._humanize_scenario_id(scenario_id),
        )
        tags = self._coerce_string_list(friendly.get("tags"))
        if not tags:
            tags = self._first_string_list(
                self._lookup_value(manifest, ("tags", "scenario_tags")),
                self._lookup_value(dataset_profile, ("tags", "scenario_tags")),
            )
        dataset = self._first_string(
            friendly.get("dataset"),
            self._lookup_value(
                manifest,
                ("dataset", "dataset_name", "dataset_id"),
            ),
            self._lookup_value(
                dataset_profile,
                ("dataset", "dataset_name", "dataset_id"),
            ),
        )
        model = self._first_string(
            friendly.get("model"),
            self._lookup_value(manifest, ("model", "model_name", "base_model")),
            self._lookup_value(
                dataset_profile,
                ("model", "model_name", "base_model"),
            ),
        )
        has_images = dataset == "AMAZON_BEAUTY_POC" and bool(
            self._load_image_manifest().get("items")
        )

        return {
            "id": scenario_id,
            "name": name,
            "display_name": name,
            "path": self._public_scenario_path(scenario_dir),
            "available_files": available_files,
            "dataset": dataset,
            "model": model,
            "description": self._first_string(
                self._lookup_value(frontend_summary, ("headline",)),
                self._lookup_value(manifest, ("description", "summary")),
                self._lookup_value(dataset_profile, ("description", "summary")),
            ),
            "tags": tags,
            "has_v3": is_v3,
            "available_panels": available_panels,
            "supported_directions": supported_directions,
            "has_runtime": self._has_v3_panel(scenario_dir, "v3_runtime"),
            "has_curves": self._has_v3_panel(scenario_dir, "v3_curves"),
            "has_target_manipulation": self._has_v3_panel(
                scenario_dir,
                "v3_target_manipulation",
            ),
            "has_membership": self._has_v3_panel(scenario_dir, "v3_membership"),
            "has_update_leakage": self._has_v3_panel(
                scenario_dir,
                "v3_update_leakage",
            ),
            "has_aggregation_defense": self._has_v3_panel(
                scenario_dir,
                "v3_aggregation_defense",
            ),
            "has_privacy_defense": self._has_v3_panel(
                scenario_dir,
                "v3_privacy_defense",
            ),
            "has_model_support": self._has_v3_panel(
                scenario_dir,
                "v3_model_support",
            ),
            "is_display_ready": bool(available_files),
            "has_recommendations": (
                ARTIFACT_SPECS["recommendation_comparison"].file_name
                in available_files
            ),
            "has_privacy": (
                ARTIFACT_SPECS["privacy_risk_summary"].file_name
                in available_files
            ),
            "has_metrics": (
                ARTIFACT_SPECS["metrics_summary"].file_name
                in available_files
            ),
            "has_images": has_images,
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
            if warning.get("code") not in {"missing_artifact", "missing_panel"}
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
            missing_code = "missing_panel" if spec.key in V3_ARTIFACT_KEYS else "missing_artifact"
            return ArtifactReadResult(
                data=None,
                missing=True,
                warnings=[
                    self._warning(
                        missing_code,
                        f"{spec.file_name} is not available for this scenario.",
                        spec.file_name,
                    )
                ],
            )

        try:
            data = self._read_json_file(file_path)
            if preview and spec.key == "recommendation_comparison":
                data = self._preview_recommendation_payload(data, scenario_dir)
            public_data = self._publicize_payload(data, scenario_dir)
            if spec.key in V3_ARTIFACT_KEYS:
                public_data = self._decorate_v3_payload(public_data, spec)
            return ArtifactReadResult(
                data=public_data,
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

    def _read_json_file(self, file_path: Path) -> Any:
        stat = file_path.stat()
        cache_entry = self._json_cache.get(file_path)
        if cache_entry and cache_entry[0] == stat.st_mtime:
            return cache_entry[1]

        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        self._json_cache[file_path] = (stat.st_mtime, data)
        return data

    def _get_artifact_spec(self, artifact_key: str) -> ArtifactSpec:
        try:
            return ARTIFACT_SPECS[artifact_key]
        except KeyError as exc:
            raise ValueError(f"Unknown showcase artifact key: {artifact_key}") from exc

    def _get_v3_artifact_key(self, route_panel_key: str) -> str:
        try:
            return V3_ROUTE_PANEL_KEYS[route_panel_key]
        except KeyError as exc:
            raise ValueError(f"Unknown showcase V3 panel: {route_panel_key}") from exc

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
        if self._is_v3_scenario(scenario_dir):
            return V3_EXPECTED_ARTIFACT_FILES
        if self._is_matrix_scenario(scenario_dir):
            return MATRIX_EXPECTED_ARTIFACT_FILES
        return STANDARD_EXPECTED_ARTIFACT_FILES

    def _is_v3_scenario(self, scenario_dir: Path) -> bool:
        return any((scenario_dir / ARTIFACT_SPECS[key].file_name).is_file() for key in V3_ARTIFACT_KEYS)

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

    def _available_v3_panels(self, scenario_dir: Path) -> List[str]:
        return [
            ARTIFACT_SPECS[key].response_key
            for key in V3_ARTIFACT_KEYS
            if (scenario_dir / ARTIFACT_SPECS[key].file_name).is_file()
        ]

    def _has_v3_panel(self, scenario_dir: Path, artifact_key: str) -> bool:
        return (scenario_dir / ARTIFACT_SPECS[artifact_key].file_name).is_file()

    def _supported_v3_directions(
        self,
        scenario_dir: Path,
        profile: Dict[str, Any],
        frontend_summary: Dict[str, Any],
    ) -> List[str]:
        directions = self._coerce_string_list(
            profile.get("supported_frontend_directions")
        )
        if directions:
            return directions

        direction_cards = frontend_summary.get("direction_cards")
        if isinstance(direction_cards, list):
            directions = [
                direction
                for card in direction_cards
                if isinstance(card, dict)
                if (direction := self._coerce_string(card.get("direction")))
            ]
            if directions:
                return directions

        return [
            direction
            for direction, artifact_key in V3_DIRECTION_PANEL_KEYS.items()
            if self._has_v3_panel(scenario_dir, artifact_key)
        ]

    def _preview_recommendation_payload(self, data: Any, scenario_dir: Path) -> Any:
        if not isinstance(data, dict):
            return data

        preview_limit = 5
        preview_data = dict(data)
        recommendation_preview = self._build_recommendation_payload(
            data,
            scenario_dir,
            limit=preview_limit,
            column="all",
        )
        for column_key, (output_key, source_keys) in RECOMMENDATION_COLUMNS.items():
            preview_data[output_key] = recommendation_preview.get(output_key, [])
            for source_key in source_keys:
                if source_key in preview_data and source_key != output_key:
                    preview_data[source_key] = recommendation_preview.get(output_key, [])

        preview_data["preview_limit"] = preview_limit
        preview_data["total_counts"] = recommendation_preview["total_counts"]
        preview_data["has_more"] = recommendation_preview["has_more"]
        warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
        if any(recommendation_preview["has_more"].values()):
            preview_data["warnings"] = [
                *warnings,
                (
                    "recommendation_comparison is preview-limited in /report; "
                    "use /showcase/scenarios/{scenario_id}/recommendations?limit=5|15|50 "
                    "for paged recommendation rows."
                ),
            ]

        return preview_data

    def _build_recommendation_payload(
        self,
        data: Any,
        scenario_dir: Path,
        limit: int,
        column: str,
    ) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {
                "baseline_recommendations": [],
                "attack_recommendations": [],
                "defended_recommendations": [],
                "total_counts": {"baseline": 0, "attack": 0, "defense": 0},
                "has_more": {"baseline": False, "attack": False, "defense": False},
                "limit": limit,
                "column": column,
            }

        limit = max(1, min(int(limit), 50))
        selected_columns = (
            tuple(RECOMMENDATION_COLUMNS.keys())
            if column == "all"
            else (column if column in RECOMMENDATION_COLUMNS else "baseline",)
        )
        dataset = self._infer_dataset(scenario_dir)

        payload: Dict[str, Any] = {
            "baseline_recommendations": [],
            "attack_recommendations": [],
            "defended_recommendations": [],
            "total_counts": {},
            "has_more": {},
            "limit": limit,
            "column": column,
        }

        for column_key, (output_key, _) in RECOMMENDATION_COLUMNS.items():
            rows = self._recommendation_rows_for_column(data, column_key)
            total_count = len(rows)
            payload["total_counts"][column_key] = total_count
            payload["total_counts"][output_key] = total_count
            payload["has_more"][column_key] = total_count > limit
            payload["has_more"][output_key] = total_count > limit

            if column_key not in selected_columns:
                continue

            payload[output_key] = [
                self._enrich_recommendation_item(row, dataset)
                for row in rows[:limit]
            ]

        for key in (
            "note",
            "recommendation_manipulation",
            "target_items",
            "target_rank_score",
            "warnings",
        ):
            if key in data:
                payload[key] = self._publicize_value(data[key], dataset)

        return payload

    def _recommendation_rows_for_column(
        self,
        data: Dict[str, Any],
        column: str,
    ) -> List[Any]:
        _, source_keys = RECOMMENDATION_COLUMNS[column]
        for source_key in source_keys:
            value = data.get(source_key)
            if isinstance(value, list):
                return value
        return []

    def _enrich_recommendation_item(
        self,
        item: Any,
        dataset: str | None,
    ) -> Dict[str, Any]:
        if not isinstance(item, dict):
            return {"item_id": self._coerce_string(item)}

        public_item = {
            key: self._publicize_value(value, dataset)
            for key, value in item.items()
            if key != "source_file"
        }
        item_id = self._first_string(
            public_item.get("item_id"),
            public_item.get("itemID"),
            public_item.get("itemId"),
            public_item.get("id"),
            public_item.get("asin"),
            public_item.get("raw_item_id"),
            public_item.get("target_item_id"),
        )
        if item_id:
            public_item["item_id"] = item_id

        image_info = self._get_image_info(dataset, item_id) if dataset and item_id else None
        if image_info:
            public_item.setdefault("title", image_info.get("title"))
            public_item.setdefault("category", image_info.get("category"))
            public_item.setdefault("image_url", image_info.get("image_url"))
            if image_info.get("full_path"):
                public_item["local_image_url"] = (
                    f"/showcase/images/{dataset}/{quote(item_id, safe='')}?size=full"
                )
            if image_info.get("thumbnail_path"):
                public_item["thumbnail_url"] = (
                    f"/showcase/images/{dataset}/{quote(item_id, safe='')}?size=thumb"
                )

        return public_item

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
        thumbnail_dir = self._coerce_string(manifest.get("thumbnail_dir"))
        thumbnail_root = (
            self._resolve_fedvlr_path(thumbnail_dir)
            if thumbnail_dir
            else image_root / "thumbs"
        )
        items: Dict[str, Dict[str, Any]] = {}

        for item in manifest.get("items", []):
            if not isinstance(item, dict):
                continue
            local_image_path = self._coerce_string(item.get("local_image_path"))
            if not local_image_path:
                continue
            image_path = self._resolve_fedvlr_path(local_image_path)
            if not self._is_within_path(image_path, image_root):
                continue
            if not self._is_within_path(image_path, self.fedvlr_root):
                continue

            thumbnail_path: Path | None = None
            thumbnail_value = self._coerce_string(item.get("thumbnail_path"))
            if thumbnail_value:
                resolved_thumbnail = self._resolve_fedvlr_path(thumbnail_value)
                if self._is_within_path(
                    resolved_thumbnail,
                    thumbnail_root,
                ) and self._is_within_path(resolved_thumbnail, self.fedvlr_root):
                    thumbnail_path = resolved_thumbnail

            image_info = {
                "full_path": image_path,
                "thumbnail_path": thumbnail_path,
                "title": self._coerce_string(item.get("title")),
                "category": self._coerce_string(item.get("category")),
                "image_url": self._coerce_string(item.get("image_url")),
            }

            item_ids = [
                self._coerce_string(item.get("itemID")),
                self._coerce_string(item.get("item_id")),
                self._coerce_string(item.get("id")),
                self._coerce_string(item.get("raw_item_id")),
            ]
            for item_id in item_ids:
                if item_id and self._is_safe_path_segment(item_id):
                    items[item_id] = image_info

        self._image_manifest_cache = {"dataset": dataset, "items": items}
        return self._image_manifest_cache

    def _get_image_info(
        self,
        dataset: str | None,
        item_id: str | None,
    ) -> Dict[str, Any] | None:
        if not dataset or not item_id:
            return None
        if not self._is_safe_path_segment(dataset) or not self._is_safe_path_segment(item_id):
            return None
        manifest = self._load_image_manifest()
        if dataset != manifest.get("dataset"):
            return None
        image_info = manifest.get("items", {}).get(item_id)
        return image_info if isinstance(image_info, dict) else None

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
            public_value.get("target_item_id"),
        )
            image_info = self._get_image_info(dataset, item_id)
            if dataset and item_id and self._is_safe_path_segment(item_id):
                if public_value.get("local_image_url") or (
                    image_info and image_info.get("full_path")
                ):
                    public_value["local_image_url"] = (
                        f"/showcase/images/{dataset}/{quote(item_id, safe='')}?size=full"
                    )
                if public_value.get("thumbnail_url") or (
                    image_info and image_info.get("thumbnail_path")
                ):
                    public_value["thumbnail_url"] = (
                        f"/showcase/images/{dataset}/{quote(item_id, safe='')}?size=thumb"
                    )
                if image_info:
                    public_value.setdefault("title", image_info.get("title"))
                    public_value.setdefault("category", image_info.get("category"))
                    public_value.setdefault("image_url", image_info.get("image_url"))
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

    def _decorate_v3_payload(self, value: Any, spec: ArtifactSpec) -> Any:
        if not isinstance(value, dict):
            return value

        decorated = dict(value)
        display_status = self._display_status(decorated)
        if display_status:
            decorated.setdefault("display_status", display_status)

        display_warning = self._display_warning(decorated)
        if display_warning:
            decorated.setdefault("display_warning", display_warning)

        display_tags = self._display_tags(decorated, spec)
        if display_tags:
            decorated.setdefault("display_tags", display_tags)

        if spec.key == "v3_frontend_summary":
            direction_cards = decorated.get("direction_cards")
            if isinstance(direction_cards, list):
                decorated["direction_cards"] = [
                    self._decorate_direction_card(card)
                    if isinstance(card, dict)
                    else card
                    for card in direction_cards
                ]

        return decorated

    def _decorate_direction_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        decorated = dict(card)
        direction = self._coerce_string(decorated.get("direction"))
        status = self._coerce_string(decorated.get("status"))
        if status:
            decorated.setdefault(
                "display_status",
                STATUS_DISPLAY_LABELS.get(status, status),
            )
        warning = self._coerce_string(decorated.get("warning"))
        if warning:
            decorated.setdefault("display_warning", warning)
        tags = []
        if direction:
            tags.append(DIRECTION_DISPLAY_LABELS.get(direction, direction))
        if status:
            tags.append(STATUS_DISPLAY_LABELS.get(status, status))
        if tags:
            decorated.setdefault("display_tags", tags)
        return decorated

    def _display_status(self, payload: Dict[str, Any]) -> str | None:
        status = self._coerce_string(payload.get("status"))
        if status:
            return STATUS_DISPLAY_LABELS.get(status, status)
        if payload.get("formal_dp_available") is False:
            return "Formal DP 未提供"
        return None

    def _display_warning(self, payload: Dict[str, Any]) -> str | None:
        for key in ("display_warning", "warning", "warnings", "boundary", "limitation", "limitations"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    warning = self._coerce_string(item)
                    if warning:
                        return warning
            else:
                warning = self._coerce_string(value)
                if warning:
                    return warning
        return None

    def _display_tags(self, payload: Dict[str, Any], spec: ArtifactSpec) -> List[str]:
        tags = list(V3_PANEL_DISPLAY_TAGS.get(spec.key, []))
        status = self._coerce_string(payload.get("status"))
        if status:
            tags.append(STATUS_DISPLAY_LABELS.get(status, status))
        evidence_type = self._coerce_string(payload.get("evidence_type"))
        if evidence_type == "mixed_proxy":
            tags.append("混合代理证据")
        if payload.get("formal_dp_available") is False:
            tags.append("Formal DP 未实现")
        secure_aggregation = payload.get("secure_aggregation")
        if isinstance(secure_aggregation, dict) and secure_aggregation.get("demo_only"):
            tags.append("SecAgg 演示")
        if payload.get("attack_topk_hit") is False:
            tags.append("TopK 未命中")
        return list(dict.fromkeys(tags))

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
