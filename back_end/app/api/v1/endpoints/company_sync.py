import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.api.deps import mongo_db
from app.services.company_sync_service import CompanySyncAlreadyRunning, CompanySyncCancelled, CompanySyncService

logger = logging.getLogger(__name__)

router = APIRouter()


class CompanySyncCounters(BaseModel):
    processed: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    sources: dict[str, dict[str, int]] = Field(default_factory=dict)


class CompanySyncStatusResponse(BaseModel):
    job_name: str
    status: str
    run_id: str | None = None
    active_source: str | None = None
    cancel_requested: bool = False
    current_batch_number: int | None = None
    current_batch_size: int | None = None
    current_batch_progress: int | None = None
    current_insee_offset: int | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_successful_run: datetime | None = None
    last_check_at: datetime | None = None
    last_error: str | None = None
    counters: CompanySyncCounters = Field(default_factory=CompanySyncCounters)


class CompanySyncTriggerResponse(BaseModel):
    status: str
    source: str
    counters: CompanySyncCounters


class CompanySyncCancelResponse(BaseModel):
    status: str
    accepted: bool


@router.get("/company-sync", response_model=CompanySyncStatusResponse)
async def get_company_sync_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> CompanySyncStatusResponse:
    service = CompanySyncService(db)
    state = await service.get_status()
    return CompanySyncStatusResponse(**state)


@router.post("/company-sync", response_model=CompanySyncTriggerResponse)
async def trigger_company_sync(
    source: Literal["all", "insee", "inpi", "bodacc"] = Query(default="all"),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> CompanySyncTriggerResponse:
    service = CompanySyncService(db)
    try:
        await service.run(source=source)
        state = await service.get_status()
        logger.info("[endpoint] company sync triggered source=%s", source)
        return CompanySyncTriggerResponse(
            status=state.get("status", "idle"),
            source=source,
            counters=CompanySyncCounters(**state.get("counters", {})),
        )
    except CompanySyncAlreadyRunning as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except CompanySyncCancelled:
        state = await service.get_status()
        logger.info("[endpoint] company sync cancelled source=%s", source)
        return CompanySyncTriggerResponse(
            status=state.get("status", "cancelled"),
            source=source,
            counters=CompanySyncCounters(**state.get("counters", {})),
        )
    except Exception as exc:
        logger.exception("[endpoint] company sync failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/company-sync/cancel", response_model=CompanySyncCancelResponse)
async def cancel_company_sync(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> CompanySyncCancelResponse:
    service = CompanySyncService(db)
    result: dict[str, Any] = await service.request_cancel()
    logger.info("[endpoint] company sync cancel accepted=%s", result["accepted"])
    return CompanySyncCancelResponse(**result)
