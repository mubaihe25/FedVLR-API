from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.services.workbench_service import WorkbenchService, get_workbench_service


router = APIRouter(prefix="/workbench", tags=["workbench"])


@router.get("/options")
def get_workbench_options(
    service: WorkbenchService = Depends(get_workbench_service),
) -> Dict[str, Any]:
    try:
        return service.options()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/validate")
def validate_workbench_config(
    payload: Dict[str, Any] = Body(default_factory=dict),
    service: WorkbenchService = Depends(get_workbench_service),
) -> Dict[str, Any]:
    try:
        return service.validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/jobs")
def create_workbench_job(
    payload: Dict[str, Any] = Body(default_factory=dict),
    service: WorkbenchService = Depends(get_workbench_service),
) -> Dict[str, Any]:
    try:
        return service.create_job(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
def get_workbench_job(
    job_id: str,
    service: WorkbenchService = Depends(get_workbench_service),
) -> Dict[str, Any]:
    try:
        return service.get_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/logs")
def get_workbench_job_logs(
    job_id: str,
    tail: int = Query(200, ge=1, le=1000),
    service: WorkbenchService = Depends(get_workbench_service),
) -> Dict[str, Any]:
    try:
        return service.get_logs(job_id, tail=tail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/result")
def get_workbench_job_result(
    job_id: str,
    service: WorkbenchService = Depends(get_workbench_service),
) -> Dict[str, Any]:
    try:
        return service.get_result(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
