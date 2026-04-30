import logging

from app.core.config import settings
from app.db.mongodb import get_db
from app.services.company_sync_service import CompanySyncService
from app.services.ingestion_service import IngestionService
from app.services.inpi_ingestion_service import InpiIngestionService

logger = logging.getLogger(__name__)


async def ingest_entreprises_parquet() -> None:
    logger.info("[job] ingest_entreprises_parquet started")
    db = get_db()
    service = IngestionService(db)
    try:
        await service.run(settings.DATAGOUV_DATASET_SLUG)
        logger.info("[job] ingest_entreprises_parquet done")
    except Exception:
        logger.exception("[job] ingest_entreprises_parquet failed")
        await db[settings.INGESTION_STATE_COLLECTION].update_one(
            {"dataset_slug": settings.DATAGOUV_DATASET_SLUG},
            {"$set": {"status": "error"}},
            upsert=True,
        )
        raise


async def retrain_weekly() -> None:
    logger.info("[job] retrain_weekly started")
    # TODO: retrain and persist the ML artifact under ML_ARTIFACTS_DIR


async def ingest_inpi_rne_bulk() -> None:
    logger.info("[job] ingest_inpi_rne_bulk started")
    db = get_db()
    service = InpiIngestionService(db)
    try:
        await service.run()
        logger.info("[job] ingest_inpi_rne_bulk done")
    except Exception:
        logger.exception("[job] ingest_inpi_rne_bulk failed")
        await db[settings.INGESTION_STATE_COLLECTION].update_one(
            {"dataset_slug": settings.INPI_RNE_DATASET_SLUG},
            {"$set": {"status": "error"}},
            upsert=True,
        )
        raise


async def sync_company_registry() -> None:
    logger.info("[job] sync_company_registry started")
    db = get_db()
    service = CompanySyncService(db)
    try:
        await service.run()
        logger.info("[job] sync_company_registry done")
    except Exception:
        logger.exception("[job] sync_company_registry failed")
        await db[settings.COMPANY_SYNC_STATE_COLLECTION].update_one(
            {"job_name": "company_sync"},
            {"$set": {"status": "error", "last_check_at": None}},
            upsert=True,
        )
        raise
