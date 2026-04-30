import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.api.deps import mongo_db
from app.core.config import settings
from app.services.ingestion_service import IngestionAlreadyRunning, IngestionService
from app.services.inpi_ingestion_service import (
    InpiIngestionAlreadyRunning,
    InpiIngestionService,
)

logger = logging.getLogger(__name__)

router = APIRouter()
inpi_router = APIRouter()


class IngestionResponse(BaseModel):
    status: str
    rows_ingested: int | None = None
    error: str | None = None


class IngestionCancelResponse(BaseModel):
    status: str
    accepted: bool


class IngestionStatusResponse(BaseModel):
    dataset_slug: str
    status: str
    run_id: str | None = None
    cancel_requested: bool = False
    force_requested: bool | None = None
    current_file_path: str | None = None
    current_file_remote_update: datetime | None = None
    last_remote_update: datetime | None = None
    last_started_at: datetime | None = None
    last_successful_run: datetime | None = None
    last_check_at: datetime | None = None
    rows_ingested_last_run: int | None = None
    downloaded_bytes: int | None = None
    download_target: str | None = None
    last_error: str | None = None


@router.get("/ingest", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> IngestionStatusResponse:
    service = IngestionService(db)
    state = await service.get_status(settings.DATAGOUV_DATASET_SLUG)
    return IngestionStatusResponse(**state)


@router.post("/ingest", response_model=IngestionResponse)
async def trigger_ingestion(
    force: bool = Query(default=False),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> IngestionResponse:
    try:
        service = IngestionService(db)
        await service.run(settings.DATAGOUV_DATASET_SLUG, force=force)
        state = await service.get_status(settings.DATAGOUV_DATASET_SLUG)
        rows = state.get("rows_ingested_last_run", 0)
        logger.info("[endpoint] ingest triggered, rows=%d force=%s", rows, force)
        return IngestionResponse(status=state.get("status", "ok"), rows_ingested=rows)
    except IngestionAlreadyRunning as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("[endpoint] ingest failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/ingest/cancel", response_model=IngestionCancelResponse)
async def cancel_ingestion(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> IngestionCancelResponse:
    service = IngestionService(db)
    result: dict[str, Any] = await service.request_cancel(settings.DATAGOUV_DATASET_SLUG)
    logger.info("[endpoint] cancel requested accepted=%s", result["accepted"])
    return IngestionCancelResponse(**result)


# ---------------------------------------------------------------------------
# INPI RNE bulk (FTP/SFTP)
# ---------------------------------------------------------------------------

class InpiRunResponse(BaseModel):
    status: str
    files_processed: int | None = None
    rows_ingested: int | None = None
    error: str | None = None


class InpiStatusResponse(BaseModel):
    dataset_slug: str
    status: str
    run_id: str | None = None
    cancel_requested: bool = False
    force_requested: bool | None = None
    current_remote_path: str | None = None
    current_local_path: str | None = None
    downloaded_bytes: int | None = None
    remote_files_total: int | None = None
    files_processed_last_run: int | None = None
    rows_ingested_last_run: int | None = None
    last_started_at: datetime | None = None
    last_successful_run: datetime | None = None
    last_check_at: datetime | None = None
    last_error: str | None = None
    files_by_status: dict[str, int] = {}


@inpi_router.post("/inpi/run", response_model=InpiRunResponse)
async def trigger_inpi_ingestion(
    force: bool = Query(default=False),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> InpiRunResponse:
    service = InpiIngestionService(db)
    try:
        await service.run(force=force)
        state = await service.get_status()
        rows = state.get("rows_ingested_last_run", 0)
        files = state.get("files_processed_last_run", 0)
        logger.info(
            "[endpoint] inpi run done files=%s rows=%s force=%s", files, rows, force
        )
        return InpiRunResponse(
            status=state.get("status", "ok"),
            files_processed=files,
            rows_ingested=rows,
        )
    except InpiIngestionAlreadyRunning as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("[endpoint] inpi run failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@inpi_router.get("/inpi/status", response_model=InpiStatusResponse)
async def get_inpi_ingestion_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> InpiStatusResponse:
    service = InpiIngestionService(db)
    state = await service.get_status()
    return InpiStatusResponse(**state)


@inpi_router.get("/inpi/list")
async def list_inpi_remote(
    path: str | None = Query(default=None, description="Remote path to walk (defaults to INPI_REMOTE_BASE_DIR)"),
    limit: int = Query(default=200, ge=1, le=5000),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> dict[str, Any]:
    """Walk the FTP/SFTP tree and report what we see, without touching Mongo.

    Use this to diagnose listing issues (missing zips, MLSD quirks, permissions).
    """
    try:
        service = InpiIngestionService(db)
        return await service.list_remote(base=path, limit=limit)
    except Exception as exc:
        logger.exception("[endpoint] inpi list failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@inpi_router.post("/inpi/cancel", response_model=IngestionCancelResponse)
async def cancel_inpi_ingestion(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> IngestionCancelResponse:
    service = InpiIngestionService(db)
    result: dict[str, Any] = await service.request_cancel()
    logger.info("[endpoint] inpi cancel requested accepted=%s", result["accepted"])
    return IngestionCancelResponse(**result)
