from fastapi import FastAPI

from app.routes.experiments import router as experiments_router
from app.routes.health import router as health_router
from app.routes.showcase import router as showcase_router


app = FastAPI(
    title="FedVLR Read-Only API",
    version="0.1.0",
    description="A minimal read-only API for FedVLR experiment result files.",
)

app.include_router(health_router)
app.include_router(experiments_router)
app.include_router(showcase_router)
