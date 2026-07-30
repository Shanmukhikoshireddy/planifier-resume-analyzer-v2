import threading
from app.config.logging import logger
from app.services.resume.resume_scheduler import ResumeScheduler

_scheduler_thread = None
def start_scheduler():
    global _scheduler_thread
    if (
        _scheduler_thread
        and
        _scheduler_thread.is_alive()
    ):
        logger.info(
            "Resume Scheduler already running."
        )
        return
    logger.info(
        "Starting Resume Scheduler..."
    )
    scheduler = ResumeScheduler()
    _scheduler_thread = threading.Thread(
        target=scheduler.run,
        daemon=True,
        name="ResumeScheduler",
    )
    _scheduler_thread.start()
    logger.info(
        "Resume Scheduler Started."
    )