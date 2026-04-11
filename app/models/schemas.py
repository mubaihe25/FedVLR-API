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
