import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.api.deps import mongo_db
from app.schemas.ingestion import OperationCancelResponse
from app.services.financial_data_lake_service import (
    FinancialExportAlreadyRunning,
    FinancialExportCancelled,
    FinancialDataLakeService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class FinancialExportRunResponse(BaseModel):
    accepted: bool
    status: str
    run_id: str | None = None
    output_dir: str | None = None


class FinancialExportStatusResponse(BaseModel):
    dataset_slug: str
    status: str
    run_id: str | None = None
    cancel_requested: bool = False
    resource_id: str | None = None
    resource_title: str | None = None
    resource_url: str | None = None
    output_dir: str | None = None
    output_file: str | None = None
    downloaded_bytes: int = 0
    download_total_bytes: int | None = None
    download_progress_percent: float | None = None
    last_started_at: datetime | None = None
    last_successful_run: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None


@router.get(
    "/financial/resources",
    summary="List financial Parquet resources",
    description=(
        "Reads data.gouv.fr metadata for the configured financial dataset and returns available Parquet resources. "
        "Use this before starting a data-lake download."
    ),
    response_description="Financial Parquet resources available from data.gouv.fr.",
)
async def list_financial_resources(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> dict[str, Any]:
    service = FinancialDataLakeService(db)
    try:
        return await service.list_resources()
    except Exception as exc:
        logger.exception("[endpoint] financial resources failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/financial/local-files",
    summary="List local financial Parquet files",
    description="Lists financial Parquet files already registered under `/data-lake/raw/financials`.",
    response_description="Local financial data-lake files and manifests.",
)
async def list_financial_local_files(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> dict[str, Any]:
    service = FinancialDataLakeService(db)
    return await service.list_local_files()


@router.post(
    "/financial/export/run",
    response_model=FinancialExportRunResponse,
    summary="Download financial Parquet to data lake",
    description=(
        "Downloads a configured data.gouv.fr financial Parquet resource directly into "
        "`/data-lake/raw/financials/<run_name>/`, validates the Parquet magic bytes, and writes a manifest. "
        "This endpoint does not write raw financial rows to MongoDB."
    ),
    response_description="Accepted financial export run information.",
)
async def trigger_financial_export(
    background_tasks: BackgroundTasks,
    resource_id: str | None = Query(
        default=None,
        description="Optional data.gouv.fr resource id. Leave empty to use the first Parquet resource.",
    ),
    resource_url: str | None = Query(
        default=None,
        description="Optional direct Parquet resource URL. Use only when the metadata id is not available.",
    ),
    run_name: str | None = Query(
        default=None,
        description="Output folder under `/data-lake/raw/financials`. Auto-generated from the resource title if omitted.",
    ),
    overwrite: bool = Query(default=False, description="Delete and recreate the output folder if it already exists."),
    background: bool = Query(
        default=True,
        description="Run in the background and return immediately. Set false only for small resources.",
    ),
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> FinancialExportRunResponse:
    service = FinancialDataLakeService(db)
    try:
        if not background:
            await service.run(
                resource_id=resource_id,
                resource_url=resource_url,
                run_name=run_name,
                overwrite=overwrite,
            )
            state = await service.get_status()
            return FinancialExportRunResponse(
                accepted=True,
                status=state.get("status", "done"),
                run_id=state.get("run_id"),
                output_dir=state.get("output_dir"),
            )

        run_id = await service.start(
            resource_id=resource_id,
            resource_url=resource_url,
            run_name=run_name,
            overwrite=overwrite,
        )
        background_tasks.add_task(
            _run_financial_export_background,
            db,
            run_id,
            resource_id,
            resource_url,
            run_name,
            overwrite,
        )
        state = await service.get_status()
        return FinancialExportRunResponse(
            accepted=True,
            status="starting",
            run_id=run_id,
            output_dir=state.get("output_dir"),
        )
    except FinancialExportAlreadyRunning as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[endpoint] financial export failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get(
    "/financial/export/status",
    response_model=FinancialExportStatusResponse,
    summary="Get financial data-lake export status",
    description=(
        "Shows the current or last financial Parquet download, including resource metadata, output path, "
        "download progress, and error details."
    ),
    response_description="Current financial data-lake export state.",
)
async def get_financial_export_status(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> FinancialExportStatusResponse:
    service = FinancialDataLakeService(db)
    state = await service.get_status()
    return FinancialExportStatusResponse(**state)


@router.post(
    "/financial/export/cancel",
    response_model=OperationCancelResponse,
    summary="Cancel financial data-lake export",
    description="Requests cancellation of the active financial Parquet data-lake download.",
    response_description="Whether the cancellation request was accepted.",
)
async def cancel_financial_export(
    db: AsyncIOMotorDatabase = Depends(mongo_db),
) -> OperationCancelResponse:
    service = FinancialDataLakeService(db)
    result: dict[str, Any] = await service.request_cancel()
    logger.info("[endpoint] financial export cancel requested accepted=%s", result["accepted"])
    return OperationCancelResponse(**result)


async def _run_financial_export_background(
    db: AsyncIOMotorDatabase,
    run_id: str,
    resource_id: str | None,
    resource_url: str | None,
    run_name: str | None,
    overwrite: bool,
) -> None:
    service = FinancialDataLakeService(db)
    try:
        await service.run_started(
            run_id,
            resource_id=resource_id,
            resource_url=resource_url,
            run_name=run_name,
            overwrite=overwrite,
        )
    except FinancialExportCancelled:
        logger.info("[endpoint] financial export cancelled run_id=%s", run_id)
    except Exception:
        logger.exception("[endpoint] financial export background failed run_id=%s", run_id)
