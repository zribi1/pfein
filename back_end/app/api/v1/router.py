from fastapi import APIRouter

from app.api.v1.endpoints import company_sync, health, ingestion, prediction

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(prediction.router, prefix="/predictions", tags=["predictions"])
api_router.include_router(ingestion.router, prefix="/admin", tags=["admin"])
api_router.include_router(ingestion.inpi_router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(company_sync.router, prefix="/admin", tags=["admin"])
