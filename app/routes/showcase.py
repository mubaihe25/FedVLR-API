from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import (
    ShowcaseArtifactResponse,
    ShowcaseComparisonResponse,
    ShowcaseReportResponse,
    ShowcaseScenarioListResponse,
    ShowcaseSecurityResponse,
)
from app.services.result_store import ExperimentResultStore, get_result_store
from app.services.showcase_store import ShowcaseArtifactStore, get_showcase_store


router = APIRouter(prefix="/showcase", tags=["showcase"])


@router.get("/scenarios", response_model=ShowcaseScenarioListResponse)
def list_showcase_scenarios(
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> ShowcaseScenarioListResponse:
    return ShowcaseScenarioListResponse(**store.list_scenarios())


@router.get("/images/{dataset}/{item_id}", response_class=FileResponse)
def get_showcase_image(
    dataset: str,
    item_id: str,
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> FileResponse:
    image_path = store.get_image_path(dataset, item_id)
    if image_path is None:
        raise HTTPException(status_code=404, detail="Showcase image not found")
    return FileResponse(image_path)


@router.get("/scenarios/{scenario_id}/manifest", response_model=ShowcaseArtifactResponse)
def get_showcase_manifest(
    scenario_id: str,
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> ShowcaseArtifactResponse:
    try:
        return ShowcaseArtifactResponse(**store.load_artifact(scenario_id, "manifest"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/dataset", response_model=ShowcaseArtifactResponse)
def get_showcase_dataset(
    scenario_id: str,
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> ShowcaseArtifactResponse:
    try:
        return ShowcaseArtifactResponse(
            **store.load_artifact(scenario_id, "dataset_profile")
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/metrics", response_model=ShowcaseArtifactResponse)
def get_showcase_metrics(
    scenario_id: str,
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> ShowcaseArtifactResponse:
    try:
        return ShowcaseArtifactResponse(
            **store.load_artifact(scenario_id, "metrics_summary")
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/scenarios/{scenario_id}/recommendations",
    response_model=ShowcaseArtifactResponse,
)
def get_showcase_recommendations(
    scenario_id: str,
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> ShowcaseArtifactResponse:
    try:
        return ShowcaseArtifactResponse(
            **store.load_artifact(scenario_id, "recommendation_comparison")
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/security", response_model=ShowcaseSecurityResponse)
def get_showcase_security(
    scenario_id: str,
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> ShowcaseSecurityResponse:
    try:
        return ShowcaseSecurityResponse(**store.load_security(scenario_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/privacy", response_model=ShowcaseArtifactResponse)
def get_showcase_privacy(
    scenario_id: str,
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> ShowcaseArtifactResponse:
    try:
        return ShowcaseArtifactResponse(
            **store.load_artifact(scenario_id, "privacy_risk_summary")
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/report", response_model=ShowcaseReportResponse)
def get_showcase_report(
    scenario_id: str,
    store: ShowcaseArtifactStore = Depends(get_showcase_store),
) -> ShowcaseReportResponse:
    try:
        return ShowcaseReportResponse(**store.load_report(scenario_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/comparison", response_model=ShowcaseComparisonResponse)
def get_showcase_comparison(
    store: ExperimentResultStore = Depends(get_result_store),
) -> ShowcaseComparisonResponse:
    try:
        return store.get_showcase_v1_comparison()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
