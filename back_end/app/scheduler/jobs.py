import logging

logger = logging.getLogger(__name__)


async def retrain_weekly() -> None:
    logger.info("[job] retrain_weekly started")
    # TODO: retrain and persist the ML artifact under ML_ARTIFACTS_DIR
