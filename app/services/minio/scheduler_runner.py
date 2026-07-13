import threading
from app.config.logging import logger
from app.services.minio.minio_scheduler import MinioScheduler

_scheduler_thread = None
def start_scheduler():
    global _scheduler_thread
    if (
        _scheduler_thread
        and
        _scheduler_thread.is_alive()
    ):
        logger.info(
            "MinIO Scheduler already running."
        )
        return
    logger.info(
        "Starting MinIO Scheduler..."
    )
    scheduler = MinioScheduler()
    _scheduler_thread = threading.Thread(
        target=scheduler.run,
        daemon=True,
        name="MinioScheduler",
    )
    _scheduler_thread.start()
    logger.info(
        "MinIO Scheduler Started."
    )