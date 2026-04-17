from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.schemas import (
    ExperimentResultResponse,
    ExperimentSummaryListResponse,
    ExperimentSummaryResponse,
    LaunchExperimentResponse,
    LaunchStatusResponse,
)
from app.services.launcher_service import LauncherService, get_launcher_service
from app.services.result_store import ExperimentResultStore, get_result_store


router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/launch/{launch_id}", response_model=LaunchStatusResponse)
def get_launch_status(
    launch_id: str,
    launcher: LauncherService = Depends(get_launcher_service),
) -> LaunchStatusResponse:
    record = launcher.get_status(launch_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Launch record not found: {launch_id}")
    return LaunchStatusResponse(**record)


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


@router.get("/{experiment_key}/csv")
def download_experiment_csv(
    experiment_key: str,
    store: ExperimentResultStore = Depends(get_result_store),
) -> FileResponse:
    try:
        csv_path = store.get_csv_path(experiment_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename=csv_path.name,
    )


@router.post("/launch", response_model=LaunchExperimentResponse)
def launch_experiment(
    payload: Dict[str, Any] = Body(...),
    validate_only: bool = Query(False),
    dry_run: bool = Query(False),
    strict_validation: bool = Query(False),
    launcher: LauncherService = Depends(get_launcher_service),
) -> LaunchExperimentResponse:
    if isinstance(payload.get("config"), dict):
        config = payload["config"]
    else:
        config = {
            key: value
            for key, value in payload.items()
            if key not in {"validate_only", "dry_run", "strict_validation"}
        }
    body_validate_only = bool(payload.get("validate_only", False))
    body_dry_run = bool(payload.get("dry_run", False))
    body_strict_validation = bool(payload.get("strict_validation", False))
    result = launcher.launch(
        unified_config=config,
        validate_only=validate_only or body_validate_only,
        dry_run=dry_run or body_dry_run,
        strict_validation=strict_validation or body_strict_validation,
    )
    return LaunchExperimentResponse(**result)
