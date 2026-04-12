from fastapi import FastAPI

from app.routes.capabilities import router as capabilities_router
from app.routes.experiments import router as experiments_router
from app.routes.health import router as health_router
from app.routes.showcase import router as showcase_router


app = FastAPI(
    title="FedVLR API",
    version="0.1.0",
    description="A minimal API for FedVLR result files, capability metadata, and launcher validation.",
)

app.include_router(health_router)
app.include_router(capabilities_router)
app.include_router(experiments_router)
app.include_router(showcase_router)
