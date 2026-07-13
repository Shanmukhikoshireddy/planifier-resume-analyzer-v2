from loguru import logger
import sys

logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)
logger.add(
    "logs/application.log",
    rotation="10 MB",
    retention="30 days",
    level="INFO",
)
__all__ = [
    "logger",
]