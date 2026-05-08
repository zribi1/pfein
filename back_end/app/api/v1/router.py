from fastapi import APIRouter

from app.api.v1.endpoints import bodacc, financial, health, inpi, insee, pipeline, prediction

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(prediction.router, prefix="/predictions", tags=["Predictions"])
api_router.include_router(inpi.router, prefix="/ingestion", tags=["INPI"])
api_router.include_router(insee.router, prefix="/ingestion", tags=["INSEE"])
api_router.include_router(bodacc.router, prefix="/ingestion", tags=["BODACC"])
api_router.include_router(financial.router, prefix="/ingestion", tags=["Financials"])
api_router.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
