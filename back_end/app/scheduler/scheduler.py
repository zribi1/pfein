import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.scheduler import jobs

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)

scheduler.add_job(
    jobs.ingest_entreprises_parquet,
    "cron",
    hour=settings.INGESTION_CRON_HOUR,
    minute=settings.INGESTION_CRON_MINUTE,
    id="ingest_entreprises_parquet",
    replace_existing=True,
    coalesce=True,
    max_instances=1,
    misfire_grace_time=3600,
)

if settings.INPI_RNE_ENABLED:
    scheduler.add_job(
        jobs.ingest_inpi_rne_bulk,
        "cron",
        hour=settings.INPI_RNE_CRON_HOUR,
        minute=settings.INPI_RNE_CRON_MINUTE,
        id="ingest_inpi_rne_bulk",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

if settings.COMPANY_SYNC_ENABLED:
    scheduler.add_job(
        jobs.sync_company_registry,
        "cron",
        hour=settings.COMPANY_SYNC_CRON_HOUR,
        minute=settings.COMPANY_SYNC_CRON_MINUTE,
        id="sync_company_registry",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

# scheduler.add_job(
#     jobs.retrain_weekly, "cron", day_of_week="sun", hour=3,
#     id="retrain_weekly", replace_existing=True,
# )

_ = jobs  # keep import so jobs module is discovered even when all schedules are commented
