import time

from app.config.logging import logger
from app.config.settings import settings
from app.workers.resume_processor import ResumeProcessor
from app.repository.applicant_repository import ApplicantRepository


class MinioScheduler:

    def __init__(self):
        self.resume_processor = ResumeProcessor()
        self.applicant_repository = ApplicantRepository()
        self.interval = settings.SCHEDULER_INTERVAL

    # Scheduler Loop
    def run(self):
        logger.info("APPLICANT SCHEDULER STARTED")

        while True:
            try:
                self.scan_bucket()
            except Exception as e:
                logger.exception(e)

            time.sleep(self.interval)

    # Scan Applicants
    def scan_bucket(self):
        logger.info("Scanning Applicants...")

        applicants = self.applicant_repository.get_pending_applicants()
        logger.info(f"Applicants found: {len(applicants)}")

        for applicant in applicants:

            applicant_id = str(applicant["_id"])
            logger.info(f"Applicant ID: {applicant_id}")

            self.applicant_repository.update_ai_sync_status(
                applicant_id,
                "PROCESSING",
            )

            try:
                # Resume URL
                resume_url = applicant.get("resumeUrl")

                if not resume_url:
                    logger.error(
                        f"No resumeUrl found for applicant {applicant_id}"
                    )

                    self.applicant_repository.update_ai_sync_status(
                        applicant_id,
                        "FAILED",
                    )
                    continue

                # Job Position DBRef
                job_ref = applicant.get("jobPosition")

                if not job_ref:
                    logger.error(
                        f"No jobPosition found for applicant {applicant_id}"
                    )

                    self.applicant_repository.update_ai_sync_status(
                        applicant_id,
                        "FAILED",
                    )
                    continue

                # Extract ObjectId from DBRef
                job_id = str(job_ref.id)

                logger.info(f"Job ID : {job_id}")

                result = self.resume_processor.process_resume(
                    resume_url=resume_url,
                    job_id=job_id,
                    applicant_id=str(applicant["_id"]),
                )

                if result == "DUPLICATE":
                    self.applicant_repository.update_ai_sync_status(
                        applicant_id,
                        "COMPLETED",
                    )
                    continue

                if not result:
                    self.applicant_repository.update_ai_sync_status(
                        applicant_id,
                        "FAILED",
                    )
                    continue

                self.applicant_repository.update_ai_sync_status(
                    applicant_id,
                    "COMPLETED",
                )

            except Exception as e:
                logger.exception(e)

                self.applicant_repository.update_ai_sync_status(
                    applicant_id,
                    "FAILED",
                )