from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import (
    ExperimentResultResponse,
    ExperimentSummaryListResponse,
    ExperimentSummaryResponse,
)
from app.services.result_store import ExperimentResultStore, get_result_store


router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/summaries", response_model=ExperimentSummaryListResponse)
def list_experiment_summaries(
    store: ExperimentResultStore = Depends(get_result_store),
) -> ExperimentSummaryListResponse:
    items = store.list_summaries()
    return ExperimentSummaryListResponse(count=len(items), items=items)


@router.get("/{experiment_key}/summary", response_model=ExperimentSummaryResponse)
def get_experiment_summary(
    experiment_key: str,
    store: ExperimentResultStore = Depends(get_result_store),
) -> ExperimentSummaryResponse:
    try:
        return store.get_summary(experiment_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{experiment_key}/result", response_model=ExperimentResultResponse)
def get_experiment_result(
    experiment_key: str,
    store: ExperimentResultStore = Depends(get_result_store),
) -> ExperimentResultResponse:
    try:
        return store.get_result(experiment_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
