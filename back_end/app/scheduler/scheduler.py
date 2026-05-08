import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.scheduler import jobs

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)

# scheduler.add_job(
#     jobs.retrain_weekly, "cron", day_of_week="sun", hour=3,
#     id="retrain_weekly", replace_existing=True,
# )

_ = jobs  # keep import so jobs module is discovered even when all schedules are commented
