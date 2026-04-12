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
    accepted: bool
    success: bool
    launch_mode: str
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
