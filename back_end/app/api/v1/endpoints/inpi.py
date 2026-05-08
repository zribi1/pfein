import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.api.deps import mongo_db
from app.schemas.ingestion import OperationCancelResponse
from app.services.inpi_parquet_export_service import (
    InpiParquetExportAlreadyRunning,
    InpiParquetExportCancelled,
    InpiParquetExportService,
)
from app.services.inpi_source_download_service import (
    InpiSourceDownloadAlreadyRunning,
    InpiSourceDownloadCancelled,
    InpiSourceDownloadService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class InpiParquetExportRunResponse(BaseModel):
    accepted: bool
    status: str
    run_id: str | None = None
    progress_file: str | None = None


class InpiParquetExportStatusResponse(BaseModel):
    dataset_slug: str
    status: str
    run_id: str | None = None
    cancel_requested: bool = False
    discovered: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    rows: int = 0
    current_file: str | None = None
    current_category: str | None = None
    current_niveau: str | None = None
    current_output_dir: str | None = None
    failed_files: list[str] = Field(default_factory=list)
    categories_requested: list[str] | None = None
    niveaux_requested: list[str] | None = None
    last_started_at: datetime | None = None
    last_successful_run: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None


class InpiSourceDownloadRunResponse(BaseModel):
    accepted: bool
    status: str
    run_id: str | None = None


class InpiSourceDownloadStatusResponse(BaseModel):
    dataset_slug: str
    status: str
    run_id: str | None = None
    cancel_requested: bool = False
    discovered: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    current_remote_path: str | None = None
    current_local_path: str | None = None
    download_total_bytes: int | None = None
    failed_files: list[str] = Field(default_factory=list)
    categories_requested: list[str] | None = None
    niveaux_requested: list[str] | None = None
    last_started_at: datetime | None = None
    last_successful_run: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None


@router.get(
    "/inpi/source-files",
    summary="List remote INPI source files",
    description=(
        "Lists official INPI FTP/SFTP ZIP archives that match the requested family and level. "
        "This endpoint only inspects source files; it does not write raw MongoDB records."
    ),
    response_description="Remote INPI source files and local download state.",
)
async def list_inpi_source_files(
    categories: list[str] | None = Query(
        default=None,
        description="Filter by INPI family. Use `comptes_annuels`, `formalites`, or comma-separated values.",
    ),
    niveaux: list[str] | None = Query(
        default=None,
        description="Filter by INPI level. Use `standard`, `niveau1`, or comma-separated values.",
    ),
    limit: int = Query(default=200, ge=1, le=5000, description="Maximum number of remote files to return."),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> dict[str, Any]:
    service = InpiSourceDownloadService(db)
    try:
        return await service.list_remote(categories=categories, niveaux=niveaux, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[endpoint] inpi source file list failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "/inpi/source-download/run",
    response_model=InpiSourceDownloadRunResponse,
    summary="Download INPI source ZIP files",
    description=(
        "Downloads official INPI FTP/SFTP ZIP archives into `INPI_LOCAL_DATA_DIR` only. "
        "After this completes, run the INPI Parquet export endpoint to build `/data-lake/raw/inpi/...`. "
        "This clean path avoids writing raw INPI documents to MongoDB."
    ),
    response_description="Accepted download run information.",
)
async def trigger_inpi_source_download(
    background_tasks: BackgroundTasks,
    force_download: bool = Query(default=False, description="Download again even when the local ZIP exists."),
    max_files: int | None = Query(default=None, ge=1, description="Optional safety limit for testing."),
    categories: list[str] | None = Query(
        default=None,
        description="INPI families to download. Use `comptes_annuels`, `formalites`, or comma-separated values.",
    ),
    niveaux: list[str] | None = Query(
        default=None,
        description="INPI levels to download. Use `standard`, `niveau1`, or comma-separated values.",
    ),
    background: bool = Query(
        default=True,
        description="Run in the background and return immediately. Set false for small diagnostic downloads.",
    ),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> InpiSourceDownloadRunResponse:
    service = InpiSourceDownloadService(db)
    try:
        if not background:
            await service.run(
                force_download=force_download,
                max_files=max_files,
                categories=categories,
                niveaux=niveaux,
            )
            state = await service.get_status()
            return InpiSourceDownloadRunResponse(
                accepted=True,
                status=state.get("status", "done"),
                run_id=state.get("run_id"),
            )

        run_id = await service.start(
            force_download=force_download,
            max_files=max_files,
            categories=categories,
            niveaux=niveaux,
        )
        background_tasks.add_task(
            _run_inpi_source_download_background,
            db,
            run_id,
            force_download,
            max_files,
            categories,
            niveaux,
        )
        logger.info("[endpoint] inpi source download accepted run_id=%s", run_id)
        return InpiSourceDownloadRunResponse(accepted=True, status="starting", run_id=run_id)
    except InpiSourceDownloadAlreadyRunning as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[endpoint] inpi source download failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get(
    "/inpi/source-download/status",
    response_model=InpiSourceDownloadStatusResponse,
    summary="Get INPI source download status",
    description=(
        "Shows the current or last clean INPI source download run, including discovered, downloaded, skipped, "
        "and failed source ZIP counts."
    ),
    response_description="Current INPI source download state.",
)
async def get_inpi_source_download_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> InpiSourceDownloadStatusResponse:
    service = InpiSourceDownloadService(db)
    state = await service.get_status()
    return InpiSourceDownloadStatusResponse(**state)


@router.post(
    "/inpi/source-download/cancel",
    response_model=OperationCancelResponse,
    summary="Cancel INPI source download",
    description="Requests cancellation of the active clean INPI source download run.",
    response_description="Whether the cancellation request was accepted.",
)
async def cancel_inpi_source_download(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> OperationCancelResponse:
    service = InpiSourceDownloadService(db)
    result: dict[str, Any] = await service.request_cancel()
    logger.info("[endpoint] inpi source download cancel requested accepted=%s", result["accepted"])
    return OperationCancelResponse(**result)


@router.get(
    "/inpi/local-files",
    summary="List local INPI source files",
    description=(
        "Lists local INPI ZIP archives mounted under `INPI_LOCAL_DATA_DIR`, identifies their family and level, "
        "and reports whether a Parquet manifest already exists in `/data-lake/raw/inpi/...`."
    ),
    response_description="Local INPI ZIP files and export status.",
)
async def list_inpi_local_files(
    categories: list[str] | None = Query(
        default=None,
        description="Filter by INPI family. Use `comptes_annuels`, `formalites`, or comma-separated values.",
    ),
    niveaux: list[str] | None = Query(
        default=None,
        description="Filter by INPI level. Use `standard`, `niveau1`, or comma-separated values.",
    ),
    limit: int = Query(default=200, ge=1, le=5000, description="Maximum number of local files to return."),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> dict[str, Any]:
    service = InpiParquetExportService(db)
    try:
        return await service.list_local_files(categories=categories, niveaux=niveaux, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post(
    "/inpi/parquet-export/run",
    response_model=InpiParquetExportRunResponse,
    summary="Export INPI ZIP files to Parquet",
    description=(
        "Discovers local INPI RNE ZIP archives under `INPI_LOCAL_DATA_DIR` and exports them to "
        "`/data-lake/raw/inpi/<category>/<niveau>/<zip-name>/`. Use `max_records_per_file` for a small Step 4 "
        "smoke run before processing full annual-account or formality stock archives."
    ),
    response_description="Accepted run information and progress file location.",
)
async def trigger_inpi_parquet_export(
    background_tasks: BackgroundTasks,
    force_export: bool = Query(
        default=False,
        description="Delete and recreate Parquet output even when an existing manifest is present.",
    ),
    max_files: int | None = Query(
        default=None,
        ge=1,
        description="Optional safety limit for testing. Leave empty to process every discovered local ZIP.",
    ),
    max_records_per_file: int | None = Query(
        default=None,
        ge=1,
        description="Optional record cap per ZIP. Use this for smoke exports from very large INPI stocks.",
    ),
    categories: list[str] | None = Query(
        default=None,
        description="INPI families to export. Use `comptes_annuels`, `formalites`, or comma-separated values.",
    ),
    niveaux: list[str] | None = Query(
        default=None,
        description="INPI levels to export. Use `standard`, `niveau1`, or comma-separated values.",
    ),
    include_raw_json: bool = Query(
        default=False,
        description="Store full source records as compressed JSON text. Leave false for compact raw Parquet.",
    ),
    background: bool = Query(
        default=True,
        description="Run in the background and return immediately. Set false for bounded smoke exports.",
    ),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> InpiParquetExportRunResponse:
    service = InpiParquetExportService(db)
    try:
        if not background:
            await service.run(
                force_export=force_export,
                max_files=max_files,
                max_records_per_file=max_records_per_file,
                categories=categories,
                niveaux=niveaux,
                include_raw_json=include_raw_json,
            )
            state = await service.get_status()
            return InpiParquetExportRunResponse(
                accepted=True,
                status=state.get("status", "done"),
                run_id=state.get("run_id"),
                progress_file=str(service.progress_path),
            )

        run_id = await service.start(
            force_export=force_export,
            max_files=max_files,
            max_records_per_file=max_records_per_file,
            categories=categories,
            niveaux=niveaux,
            include_raw_json=include_raw_json,
        )
        background_tasks.add_task(
            _run_inpi_parquet_export_background,
            db,
            run_id,
            force_export,
            max_files,
            max_records_per_file,
            categories,
            niveaux,
            include_raw_json,
        )
        logger.info("[endpoint] inpi parquet export accepted run_id=%s", run_id)
        return InpiParquetExportRunResponse(
            accepted=True,
            status="starting",
            run_id=run_id,
            progress_file=str(service.progress_path),
        )
    except InpiParquetExportAlreadyRunning as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[endpoint] inpi parquet export failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get(
    "/inpi/parquet-export/status",
    response_model=InpiParquetExportStatusResponse,
    summary="Get INPI Parquet export status",
    description=(
        "Shows the current or last local INPI Parquet export run, including discovered ZIP count, "
        "processed/skipped/failed counters, row totals, current file, output directory, and failed files."
    ),
    response_description="Current INPI Parquet export state.",
)
async def get_inpi_parquet_export_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> InpiParquetExportStatusResponse:
    service = InpiParquetExportService(db)
    state = await service.get_status()
    return InpiParquetExportStatusResponse(**state)


@router.post(
    "/inpi/parquet-export/cancel",
    response_model=OperationCancelResponse,
    summary="Cancel INPI Parquet export",
    description=(
        "Requests cancellation of the active local INPI Parquet export run. "
        "The service checks this flag between source ZIP files."
    ),
    response_description="Whether the cancellation request was accepted.",
)
async def cancel_inpi_parquet_export(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> OperationCancelResponse:
    service = InpiParquetExportService(db)
    result: dict[str, Any] = await service.request_cancel()
    logger.info("[endpoint] inpi parquet export cancel requested accepted=%s", result["accepted"])
    return OperationCancelResponse(**result)


async def _run_inpi_parquet_export_background(
    db: AsyncIOMotorDatabase,
    run_id: str,
    force_export: bool,
    max_files: int | None,
    max_records_per_file: int | None,
    categories: list[str] | None,
    niveaux: list[str] | None,
    include_raw_json: bool,
) -> None:
    service = InpiParquetExportService(db)
    try:
        await service.run_started(
            run_id,
            force_export=force_export,
            max_files=max_files,
            max_records_per_file=max_records_per_file,
            categories=categories,
            niveaux=niveaux,
            include_raw_json=include_raw_json,
        )
    except InpiParquetExportCancelled:
        logger.info("[endpoint] inpi parquet export cancelled run_id=%s", run_id)
    except Exception:
        logger.exception("[endpoint] inpi parquet export background failed run_id=%s", run_id)


async def _run_inpi_source_download_background(
    db: AsyncIOMotorDatabase,
    run_id: str,
    force_download: bool,
    max_files: int | None,
    categories: list[str] | None,
    niveaux: list[str] | None,
) -> None:
    service = InpiSourceDownloadService(db)
    try:
        await service.run_started(
            run_id,
            force_download=force_download,
            max_files=max_files,
            categories=categories,
            niveaux=niveaux,
        )
    except InpiSourceDownloadCancelled:
        logger.info("[endpoint] inpi source download cancelled run_id=%s", run_id)
    except Exception:
        logger.exception("[endpoint] inpi source download background failed run_id=%s", run_id)
