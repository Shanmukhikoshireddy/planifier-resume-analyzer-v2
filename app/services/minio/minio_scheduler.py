import time
from app.config.logging import logger
from app.config.settings import settings
from app.repository.metadata_repository import MetadataRepository
from app.repository.minio_repository import MinioRepository
from app.workers.resume_processor import ResumeProcessor

class MinioScheduler:
    def __init__(self):
        self.minio_repository = MinioRepository()
        self.metadata_repository = MetadataRepository()
        self.resume_processor = ResumeProcessor()
        self.interval = settings.SCHEDULER_INTERVAL

    # Scheduler Loop
    def run(self):
        logger.info("MINIO SCHEDULER STARTED")
        while True:
            try:
                self.scan_bucket()
            except Exception as e:
                logger.exception(e)
            time.sleep(self.interval)

    # Scan Bucket
    def scan_bucket(self):
        logger.info("Scanning MinIO bucket...")
        objects = self.minio_repository.list_objects()
        for obj in objects:
            object_path = obj.object_name

            # Skip folders
            if object_path.endswith("/"):
                continue

            SUPPORTED_EXTENSIONS = {
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
            }

            extension = "." + object_path.lower().split(".")[-1]

            if extension not in SUPPORTED_EXTENSIONS:
                logger.info(f"Unsupported file : {object_path}")
                continue

            # Already processed?
            if self.metadata_repository.is_processed(
                object_path
            ):
                logger.info(f"Already Processed : {object_path}")
                continue

            logger.info(f"New Resume Found : {object_path}")
            self.process_resume(object_path)

    # Process Resume
    def process_resume(
        self,
        object_path: str,
    ):
        logger.info(f"Processing : {object_path}")
        try:
            # Mark Processing
            self.metadata_repository.mark_processing(
                object_path
            )

            # Process Resume
            result = self.resume_processor.process_resume(
                object_path=object_path
            )

            # Duplicate Resume
            if result == "DUPLICATE":
                logger.info(
                    f"Duplicate Resume : {object_path}"
                )
                self.metadata_repository.save_metadata(
                    object_path=object_path,
                    file_hash="",
                    status="SUCCESS",
                )
                return

            # Processing Failed
            if not result:
                logger.warning(
                    f"Resume Processing Failed : {object_path}")
                self.metadata_repository.update_status(
                    object_path,
                    "FAILED",
                )
                return

            # Processing Successful
            self.metadata_repository.save_metadata(
                object_path=object_path,
                file_hash=result,
                status="SUCCESS",
            )
            logger.info(
                f"Resume Processed Successfully : {object_path}"
            )

        except Exception as e:
            logger.exception(e)
            self.metadata_repository.update_status(
                object_path,
                "FAILED",
            ) 