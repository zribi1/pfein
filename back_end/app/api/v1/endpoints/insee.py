import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.api.deps import mongo_db
from app.schemas.ingestion import OperationCancelResponse
from app.services.insee_bulk_service import (
    InseeBulkAlreadyRunning,
    InseeBulkCancelled,
    InseeBulkService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class InseeBulkRunResponse(BaseModel):
    accepted: bool
    status: str
    run_id: str | None = None


class InseeBulkStatusResponse(BaseModel):
    dataset_slug: str
    status: str
    run_id: str | None = None
    cancel_requested: bool = False
    discovered: int = 0
    downloaded: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    rows: int = 0
    current_file: str = ""
    current_file_downloaded_bytes: int = 0
    current_file_total_bytes: int | None = None
    current_file_progress_percent: float | None = None
    failed_files: list[str] = Field(default_factory=list)
    last_started_at: datetime | None = None
    last_successful_run: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None


@router.get(
    "/insee/bulk/resources",
    summary="List INSEE Sirene bulk resources",
    description="Lists downloadable INSEE Sirene bulk resources from data.gouv.fr.",
)
async def list_insee_bulk_resources(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> dict[str, Any]:
    service = InseeBulkService(db)
    try:
        return await service.list_resources()
    except Exception as exc:
        logger.exception("[endpoint] insee bulk resources failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/insee/bulk/local-files",
    summary="List local INSEE bulk source files",
    description="Lists preserved INSEE bulk files under `/source-archives/insee/bulk` and their raw Parquet export state.",
)
async def list_insee_bulk_local_files(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> dict[str, Any]:
    service = InseeBulkService(db)
    return await service.list_local_files()


@router.post(
    "/insee/bulk/run",
    response_model=InseeBulkRunResponse,
    summary="Download/export INSEE Sirene bulk files",
    description=(
        "Primary INSEE path. Downloads official bulk files to `/source-archives/insee/bulk`, "
        "then exports them to `/data-lake/raw/insee/bulk`."
    ),
)
async def trigger_insee_bulk(
    background_tasks: BackgroundTasks,
    resource_id: str | None = Query(default=None, description="Optional data.gouv.fr resource id."),
    resource_url: str | None = Query(default=None, description="Optional direct resource URL."),
    download: bool = Query(default=True, description="Download selected bulk resources into source archives."),
    export: bool = Query(default=True, description="Export local bulk source files to raw Parquet."),
    overwrite: bool = Query(default=False, description="Overwrite existing source/raw outputs."),
    max_files: int | None = Query(default=None, ge=1, description="Optional safety limit."),
    count_rows: bool = Query(default=False, description="Count rows for manifests. Slower."),
    background: bool = Query(default=True),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> InseeBulkRunResponse:
    service = InseeBulkService(db)
    try:
        run_id = await service.start(
            resource_id=resource_id,
            resource_url=resource_url,
            download=download,
            export=export,
            overwrite=overwrite,
            max_files=max_files,
            count_rows=count_rows,
        )
        if not background:
            await service.run_started(
                run_id,
                resource_id=resource_id,
                resource_url=resource_url,
                download=download,
                export=export,
                overwrite=overwrite,
                max_files=max_files,
                count_rows=count_rows,
            )
            state = await service.get_status()
            return InseeBulkRunResponse(accepted=True, status=state.get("status", "done"), run_id=state.get("run_id"))
        background_tasks.add_task(
            _run_insee_bulk_background,
            db,
            run_id,
            resource_id,
            resource_url,
            download,
            export,
            overwrite,
            max_files,
            count_rows,
        )
        return InseeBulkRunResponse(accepted=True, status="starting", run_id=run_id)
    except InseeBulkAlreadyRunning as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[endpoint] insee bulk failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get(
    "/insee/bulk/status",
    response_model=InseeBulkStatusResponse,
    summary="Get INSEE bulk status",
)
async def get_insee_bulk_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> InseeBulkStatusResponse:
    service = InseeBulkService(db)
    state = await service.get_status()
    return InseeBulkStatusResponse(**state)


@router.post(
    "/insee/bulk/cancel",
    response_model=OperationCancelResponse,
    summary="Cancel INSEE bulk run",
)
async def cancel_insee_bulk(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> OperationCancelResponse:
    service = InseeBulkService(db)
    result: dict[str, Any] = await service.request_cancel()
    return OperationCancelResponse(**result)


async def _run_insee_bulk_background(
    db: AsyncIOMotorDatabase,
    run_id: str,
    resource_id: str | None,
    resource_url: str | None,
    download: bool,
    export: bool,
    overwrite: bool,
    max_files: int | None,
    count_rows: bool,
) -> None:
    service = InseeBulkService(db)
    try:
        await service.run_started(
            run_id,
            resource_id=resource_id,
            resource_url=resource_url,
            download=download,
            export=export,
            overwrite=overwrite,
            max_files=max_files,
            count_rows=count_rows,
        )
    except InseeBulkCancelled:
        logger.info("[endpoint] insee bulk cancelled run_id=%s", run_id)
    except Exception:
        logger.exception("[endpoint] insee bulk background failed run_id=%s", run_id)
