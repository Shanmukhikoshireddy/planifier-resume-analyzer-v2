from app.config.logging import logger
from app.dto.request.minio_event import MinioEvent
from app.repository.minio_repository import MinioRepository
from app.workers.resume_processor import ResumeProcessor

class WebhookService:
    def __init__(self):
        self.minio_repository = MinioRepository()
        self.resume_processor = ResumeProcessor()

    # Process MinIO Event
    def process_event(
        self,
        event: MinioEvent,
    ) -> None:
        logger.info("MINIO EVENT RECEIVED")
        logger.info(
            f"Bucket      : {event.bucket_name}"
        )
        logger.info(
            f"Object      : {event.object_name}"
        )
        logger.info(
            f"Event       : {event.event_name}"
        )
        logger.info(
            f"Size        : {event.file_size}"
        )

        # Process only upload events
        if not event.event_name.startswith("s3:ObjectCreated"):
            logger.info(
                "Ignoring non ObjectCreated event."
            )
            return

        # Verify object exists
        if not self.minio_repository.file_exists(
            event.object_name,
        ):
            logger.error(
                f"Object not found : {event.object_name}"
            )
            return
        logger.info(
            "Object verified successfully."
        )

        # Start Resume Processing
        self.resume_processor.process_resume(
            object_name=event.object_name
        )
        logger.info(
            f"Processing completed : {event.object_name}"
        )