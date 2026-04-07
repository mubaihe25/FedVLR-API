from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str


class ExperimentSummaryItem(BaseModel):
    experiment_key: str
    file_name: str
    relative_path: str
    has_result: bool = Field(default=False)
    summary: Dict[str, Any]


class ExperimentSummaryListResponse(BaseModel):
    count: int
    items: List[ExperimentSummaryItem]


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
