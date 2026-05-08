import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.api.deps import mongo_db
from app.schemas.ingestion import OperationCancelResponse
from app.services.bodacc_init_service import (
    BodaccInitAlreadyRunning,
    BodaccInitCancelled,
    BodaccInitIngestionService,
)
from app.services.bodacc_label_export_service import (
    BodaccLabelExportAlreadyRunning,
    BodaccLabelExportCancelled,
    BodaccLabelExportService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class BodaccLabelExportRunResponse(BaseModel):
    accepted: bool
    status: str
    run_id: str | None = None
    progress_file: str | None = None


class BodaccLabelExportStatusResponse(BaseModel):
    dataset_slug: str
    status: str
    run_id: str | None = None
    cancel_requested: bool = False
    discovered: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    rows: int = 0
    downloaded: int = 0
    download_skipped: int = 0
    redownloaded: int = 0
    current_file: str | None = None
    current_remote_path: str | None = None
    current_family: str | None = None
    current_year: int | None = None
    current_archive_size_bytes: int | None = None
    downloaded_bytes: int | None = None
    download_total_bytes: int | None = None
    download_progress_percent: float | None = None
    download_status: str | None = None
    failed_files: list[str] = Field(default_factory=list)
    families_requested: list[str] = Field(default_factory=list)
    last_started_at: datetime | None = None
    last_successful_run: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None


@router.post(
    "/bodacc/label-export/run",
    response_model=BodaccLabelExportRunResponse,
    summary="Initialize BODACC label archives",
    description=(
        "Starts the portable BODACC label-source initialization flow. The job lists the DILA current-year feed, "
        "downloads missing or unreadable `PCL` and `RCS-B` `.taz` archives into the configured data volume, "
        "validates each tar archive, and exports event rows to `/data-lake/raw/bodacc/current/...`. "
        "Use this endpoint instead of local PowerShell scripts when setting up another PC."
    ),
    response_description="Accepted run information and progress file location.",
)
async def trigger_bodacc_label_export(
    background_tasks: BackgroundTasks,
    force_download: bool = Query(
        default=False,
        description="Download archives again even when a readable local `.taz` already exists.",
    ),
    force_export: bool = Query(
        default=False,
        description="Regenerate Parquet output even when an existing manifest already has rows.",
    ),
    max_files: int | None = Query(
        default=None,
        ge=1,
        description="Optional safety limit for testing. Leave empty to process every discovered archive.",
    ),
    families: list[str] | None = Query(
        default=None,
        description="BODACC archive families to process. Repeat or comma-separate values. Defaults to `PCL,RCS-B`.",
    ),
    background: bool = Query(
        default=True,
        description="Run in the background and return immediately. Set false only for short diagnostic runs.",
    ),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> BodaccLabelExportRunResponse:
    service = BodaccLabelExportService(db)
    selected_families = _parse_family_query(families)
    try:
        if not background:
            await service.run(
                force_download=force_download,
                force_export=force_export,
                max_files=max_files,
                families=selected_families,
            )
            state = await service.get_status()
            return BodaccLabelExportRunResponse(
                accepted=True,
                status=state.get("status", "done"),
                run_id=state.get("run_id"),
                progress_file=str(service.progress_path),
            )

        run_id = await service.start(
            force_download=force_download,
            force_export=force_export,
            max_files=max_files,
            families=selected_families,
        )
        background_tasks.add_task(
            _run_bodacc_label_export_background,
            db,
            run_id,
            force_download,
            force_export,
            max_files,
            selected_families,
        )
        logger.info("[endpoint] bodacc label export accepted run_id=%s", run_id)
        return BodaccLabelExportRunResponse(
            accepted=True,
            status="starting",
            run_id=run_id,
            progress_file=str(service.progress_path),
        )
    except BodaccLabelExportAlreadyRunning as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[endpoint] bodacc label export failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get(
    "/bodacc/label-export/status",
    response_model=BodaccLabelExportStatusResponse,
    summary="Get BODACC label export status",
    description=(
        "Shows the current or last BODACC label export run, including discovered archive count, "
        "processed/skipped/failed counters, row totals, current file, download progress, and failed files."
    ),
    response_description="Current BODACC label export state.",
)
async def get_bodacc_label_export_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> BodaccLabelExportStatusResponse:
    service = BodaccLabelExportService(db)
    state = await service.get_status()
    return BodaccLabelExportStatusResponse(**state)


@router.post(
    "/bodacc/label-export/cancel",
    response_model=OperationCancelResponse,
    summary="Cancel BODACC label export",
    description=(
        "Requests cancellation of the active BODACC label export run. "
        "The service checks this flag between downloads and archive processing steps."
    ),
    response_description="Whether the cancellation request was accepted.",
)
async def cancel_bodacc_label_export(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> OperationCancelResponse:
    service = BodaccLabelExportService(db)
    result: dict[str, Any] = await service.request_cancel()
    logger.info("[endpoint] bodacc label export cancel requested accepted=%s", result["accepted"])
    return OperationCancelResponse(**result)


async def _run_bodacc_label_export_background(
    db: AsyncIOMotorDatabase,
    run_id: str,
    force_download: bool,
    force_export: bool,
    max_files: int | None,
    families: list[str] | None,
) -> None:
    service = BodaccLabelExportService(db)
    try:
        await service.run_started(
            run_id,
            force_download=force_download,
            force_export=force_export,
            max_files=max_files,
            families=families,
        )
    except BodaccLabelExportCancelled:
        logger.info("[endpoint] bodacc label export cancelled run_id=%s", run_id)
    except Exception:
        logger.exception("[endpoint] bodacc label export background failed run_id=%s", run_id)


def _parse_family_query(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    families: list[str] = []
    for value in values:
        families.extend(part.strip() for part in value.split(",") if part.strip())
    return families or None


class BodaccInitRunResponse(BaseModel):
    accepted: bool
    status: str
    run_id: str | None = None


class BodaccInitStatusResponse(BaseModel):
    dataset_slug: str
    status: str
    run_id: str | None = None
    cancel_requested: bool = False
    remote_files_total: int = 0
    files_processed_last_run: int = 0
    rows_ingested_last_run: int = 0
    files_by_status: dict[str, int] = Field(default_factory=dict)
    current_remote_path: str | None = None
    current_local_path: str | None = None
    current_year: int | None = None
    current_archive_size_bytes: int | None = None
    downloaded_bytes: int | None = None
    download_total_bytes: int | None = None
    download_progress_percent: float | None = None
    download_status: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_successful_run: datetime | None = None
    last_check_at: datetime | None = None
    last_error: str | None = None


@router.post(
    "/bodacc/init/run",
    response_model=BodaccInitRunResponse,
    summary="Initialize historical BODACC archives",
    description=(
        "Starts the historical BODACC initialization flow. It discovers all archives from the `FluxHistorique` DILA endpoint, "
        "reconciles them against the database, downloads missing/unprocessed ones, and imports them."
    ),
    response_description="Accepted run information.",
)
async def trigger_bodacc_init(
    background_tasks: BackgroundTasks,
    force: bool = Query(
        default=False,
        description="Re-process files even if they are marked as fully_processed.",
    ),
    max_files: int | None = Query(
        default=None,
        ge=1,
        description="Optional limit for testing. Overrides the config limit if set.",
    ),
    filename_contains: str | None = Query(
        default=None,
        description="Only process archives whose filename contains this substring (case-insensitive).",
    ),
    background: bool = Query(
        default=True,
        description="Run in the background and return immediately.",
    ),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> BodaccInitRunResponse:
    service = BodaccInitIngestionService(db, mode="init")
    try:
        if not background:
            await service.run_init(
                force=force,
                max_files=max_files,
                filename_contains=filename_contains,
            )
            state = await service.get_status()
            return BodaccInitRunResponse(
                accepted=True,
                status=state.get("status", "done"),
                run_id=state.get("run_id"),
            )

        # Start the background task
        # acquire_run is implicitly called inside run_init, but we need run_id now.
        # Actually, bodacc_init_service's run_init doesn't return the run_id, it just runs it.
        # To make it truly async like bodacc_label_export, we can just run it in the background.
        # Since run_init handles the full lifecycle and state updates.
        background_tasks.add_task(
            _run_bodacc_init_background,
            db,
            force,
            max_files,
            filename_contains,
        )
        logger.info("[endpoint] bodacc init accepted")
        return BodaccInitRunResponse(
            accepted=True,
            status="starting",
        )
    except BodaccInitAlreadyRunning as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[endpoint] bodacc init failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get(
    "/bodacc/init/status",
    response_model=BodaccInitStatusResponse,
    summary="Get BODACC init status",
    description="Shows the current or last BODACC historical initialization state.",
    response_description="Current BODACC historical init state.",
)
async def get_bodacc_init_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> BodaccInitStatusResponse:
    service = BodaccInitIngestionService(db, mode="init")
    state = await service.get_status()
    return BodaccInitStatusResponse(**state)


@router.post(
    "/bodacc/init/cancel",
    response_model=OperationCancelResponse,
    summary="Cancel BODACC init",
    description="Requests cancellation of the active BODACC historical initialization run.",
    response_description="Whether the cancellation request was accepted.",
)
async def cancel_bodacc_init(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> OperationCancelResponse:
    service = BodaccInitIngestionService(db, mode="init")
    result: dict[str, Any] = await service.request_cancel()
    logger.info("[endpoint] bodacc init cancel requested accepted=%s", result["accepted"])
    return OperationCancelResponse(**result)


async def _run_bodacc_init_background(
    db: AsyncIOMotorDatabase,
    force: bool,
    max_files: int | None,
    filename_contains: str | None,
) -> None:
    service = BodaccInitIngestionService(db, mode="init")
    try:
        await service.run_init(
            force=force,
            max_files=max_files,
            filename_contains=filename_contains,
        )
    except BodaccInitCancelled:
        logger.info("[endpoint] bodacc init cancelled")
    except BodaccInitAlreadyRunning:
        pass
    except Exception:
        logger.exception("[endpoint] bodacc init background failed")
