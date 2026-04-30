import asyncio
import logging
import signal

from app.core.logging import setup_logging
from app.db.mongodb import mongodb
from app.ml.loader import ml_registry
from app.scheduler.scheduler import scheduler

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    await mongodb.connect()
    ml_registry.load()
    scheduler.start()
    logger.info("worker started; scheduled jobs: %s", [j.id for j in scheduler.get_jobs()])

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
    except NotImplementedError:
        # Windows event loop doesn't support add_signal_handler; rely on KeyboardInterrupt.
        pass

    try:
        await stop.wait()
    finally:
        logger.info("worker shutting down")
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await mongodb.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
