from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import ShowcaseComparisonResponse
from app.services.result_store import ExperimentResultStore, get_result_store


router = APIRouter(prefix="/showcase", tags=["showcase"])


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
