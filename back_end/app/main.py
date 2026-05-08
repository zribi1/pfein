from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.mongodb import mongodb
from app.ml.loader import ml_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await mongodb.connect()
    ml_registry.load()
    try:
        yield
    finally:
        await mongodb.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    openapi_tags=[
        {"name": "Health", "description": "Runtime health checks for the API and MongoDB."},
        {"name": "Predictions", "description": "Continuity-risk prediction lookup endpoints."},
        {"name": "INPI", "description": "INPI/RNE source discovery, ingestion, and data-lake Parquet exports."},
        {"name": "INSEE", "description": "INSEE Sirene identity exports for the company identity backbone."},
        {"name": "BODACC", "description": "BODACC legal-event and label-source data-lake operations."},
        {"name": "Financials", "description": "Financial Parquet source discovery and data-lake downloads."},
    ],
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
