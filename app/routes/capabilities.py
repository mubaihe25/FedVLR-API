from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import CapabilitiesResponse, ExperimentSchemaResponse
from app.services.capability_store import CapabilityStore, get_capability_store


router = APIRouter(tags=["capabilities"])


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities(
    store: CapabilityStore = Depends(get_capability_store),
) -> CapabilitiesResponse:
    try:
        return CapabilitiesResponse(**store.get_capabilities())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/experiment-schema", response_model=ExperimentSchemaResponse)
def get_experiment_schema(
    store: CapabilityStore = Depends(get_capability_store),
) -> ExperimentSchemaResponse:
    try:
        return ExperimentSchemaResponse(**store.get_experiment_schema())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
