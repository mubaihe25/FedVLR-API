from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str


class ExperimentSummaryListItem(BaseModel):
    experiment_key: str
    file_name: str
    relative_path: str
    experiment_id: str | None = None
    model: str | None = None
    dataset: str | None = None
    experiment_mode: str | None = None
    scenario_tags: List[str] = Field(default_factory=list)
    active_attacks: List[str] = Field(default_factory=list)
    active_defenses: List[str] = Field(default_factory=list)
    active_privacy_metrics: List[str] = Field(default_factory=list)
    final_eval: Dict[str, Any] = Field(default_factory=dict)


class ExperimentSummaryListResponse(BaseModel):
    count: int
    items: List[ExperimentSummaryListItem]


class ExperimentSummaryResponse(BaseModel):
    experiment_key: str
    file_name: str
    relative_path: str
    summary: Dict[str, Any]


class ExperimentResultResponse(BaseModel):
    experiment_key: str
    file_name: str
    relative_path: str
    result: Dict[str, Any]


class ShowcaseComparisonResponse(BaseModel):
    source: str
    comparison_type: str
    updated_at: str | None = None
    item_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    items: List[Dict[str, Any]] = Field(default_factory=list)


class ShowcaseWarning(BaseModel):
    code: str
    message: str
    file: str | None = None


class ShowcaseScenarioItem(BaseModel):
    id: str
    name: str | None = None
    display_name: str | None = None
    path: str
    available_files: List[str] = Field(default_factory=list)
    dataset: str | None = None
    model: str | None = None
    description: str | None = None
    tags: List[str] = Field(default_factory=list)
    is_display_ready: bool = False
    has_recommendations: bool = False
    has_privacy: bool = False
    has_metrics: bool = False
    has_images: bool = False
    has_v3: bool = False
    available_panels: List[str] = Field(default_factory=list)
    supported_directions: List[str] = Field(default_factory=list)
    has_runtime: bool = False
    has_curves: bool = False
    has_target_manipulation: bool = False
    has_membership: bool = False
    has_update_leakage: bool = False
    has_aggregation_defense: bool = False
    has_privacy_defense: bool = False
    has_model_support: bool = False
    warnings: List[ShowcaseWarning] = Field(default_factory=list)


class ShowcaseScenarioListResponse(BaseModel):
    count: int
    items: List[ShowcaseScenarioItem] = Field(default_factory=list)
    warnings: List[ShowcaseWarning] = Field(default_factory=list)


class ShowcaseArtifactResponse(BaseModel):
    scenario_id: str
    artifact: str
    file: str
    data: Any | None = None
    warnings: List[ShowcaseWarning] = Field(default_factory=list)


class ShowcaseSecurityResponse(BaseModel):
    scenario_id: str
    attack_defense_summary: Any | None = None
    defense_trace: Any | None = None
    warnings: List[ShowcaseWarning] = Field(default_factory=list)


class ShowcaseReportResponse(BaseModel):
    scenario_id: str
    manifest: Any | None = None
    dataset_profile: Any | None = None
    metrics_summary: Any | None = None
    attack_defense_summary: Any | None = None
    recommendation_comparison: Any | None = None
    defense_trace: Any | None = None
    privacy_risk_summary: Any | None = None
    model_security_capability_matrix: Any | None = None
    supported_demos: Any | None = None
    unsupported_reasons: Any | None = None
    recommended_frontend_labels: Any | None = None
    warnings: List[ShowcaseWarning] = Field(default_factory=list)


class ShowcaseV3ReportResponse(BaseModel):
    scenario_id: str
    profile: Any | None = None
    runtime: Any | None = None
    curves: Any | None = None
    target_manipulation: Any | None = None
    membership: Any | None = None
    update_leakage: Any | None = None
    aggregation_defense: Any | None = None
    privacy_defense: Any | None = None
    model_support: Any | None = None
    frontend_summary: Any | None = None
    warnings: List[ShowcaseWarning] = Field(default_factory=list)


class CapabilitiesResponse(BaseModel):
    source: str
    updated_at: str | None = None
    model_count: int
    attack_count: int
    defense_count: int
    privacy_metric_count: int
    validated_combination_count: int
    data: Dict[str, Any] = Field(default_factory=dict)


class ExperimentSchemaResponse(BaseModel):
    source: str
    updated_at: str | None = None
    required_fields: List[str] = Field(default_factory=list)
    data: Dict[str, Any] = Field(default_factory=dict)


class LaunchExperimentRequest(BaseModel):
    config: Dict[str, Any] = Field(default_factory=dict)
    validate_only: bool = False
    dry_run: bool = False
    strict_validation: bool = False


class LaunchExperimentResponse(BaseModel):
    launch_id: str | None = None
    accepted: bool
    success: bool
    status: str | None = None
    launch_mode: str
    submitted_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    pid: int | None = None
    command: List[str] = Field(default_factory=list)
    return_code: int | None = None
    experiment_id: str | None = None
    result_dir: str | None = None
    summary_path: str | None = None
    result_path: str | None = None
    csv_path: str | None = None
    validation_warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    stdout_tail: str | None = None
    stderr_tail: str | None = None
    launcher_payload: Dict[str, Any] = Field(default_factory=dict)
    config_summary: Dict[str, Any] = Field(default_factory=dict)
    validate_only: bool = False
    dry_run: bool = False
    strict_validation: bool = False


class LaunchStatusResponse(LaunchExperimentResponse):
    pass
