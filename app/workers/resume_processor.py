from datetime import datetime
from pathlib import Path
from app.config.logging import logger
from app.config.settings import settings
from app.repository.profile_repository import ProfileRepository
from app.services.ingestion.parser_service import ParserService
from app.services.ingestion.embedding_service import EmbeddingService
from app.services.ingestion.duplicate_service import DuplicateService
from app.services.llm.resume_extractor_service import ResumeExtractorService
from app.utils.hash import generate_hash
from app.services.shared.pdf_converter_service import (
    PdfConverterService,
)
from urllib.parse import urlparse
import os
import tempfile
import requests
from app.repository.applicant_repository import ApplicantRepository
from app.repository.job_position_repository import JobPositionRepository
class ResumeProcessor:

    def __init__(self):

        self.profile_repository = ProfileRepository()
        self.job_position_repository = JobPositionRepository()

        self.parser_service = ParserService()

        self.embedding_service = EmbeddingService()

        self.duplicate_service = DuplicateService()

        self.resume_extractor = ResumeExtractorService()

        self.converter = PdfConverterService()

    # Process Resume
    def process_resume(
        self,
        resume_url: str,
        job_id: str,
        applicant_id: str,
    ):
        logger.info(
            f"Processing Resume : {resume_url}"
        )
        local_resume = None
        file_hash = ""
        try:

            # Download Resume
            local_resume = self._download_resume(
            resume_url
            )

            pdf_resume = None

            if local_resume.suffix.lower() == ".docx":

                logger.info(
                    "Converting DOCX to PDF..."
                )


                pdf_resume = self.converter.convert_docx_to_pdf(
                    str(local_resume)
                )

                logger.info(
                    f"PDF Created : {pdf_resume}"
                )

            # Parse Resume
            parsed_resume = self._parse_resume(
                local_resume
            )
            raw_text = parsed_resume["raw_text"]

            # Generate SHA-256
            file_hash = generate_hash(
                raw_text
            )

            # Duplicate Validation
            self._check_duplicate(
                file_hash
            )

            # Extract Structured Resume
            structured_resume = self._extract_resume(
                raw_text
            )

            # Derive Job Position From MinIO Folder
            # Get Job Position from job_positions collection
            job = self.job_position_repository.get_job_position(job_id)

            if not job:
                raise ValueError(f"Job Position not found for Job ID: {job_id}")

            job_position = job.get("title", "")

            structured_resume["job_id"] = job_id
            structured_resume["job_position"] = job_position

            logger.info(f"Job Position : {job_position}")
            structured_resume["file_hash"] = file_hash
            structured_resume["raw_text"] = raw_text
            structured_resume["file_name"] = Path(
                resume_url
            ).name
        
            # Generate Embedding
            embedding = self._generate_embedding(
                structured_resume
            )

            # Save Candidate Profile
            resume_path = resume_url

            profile_id = self._save_profile(
                resume=structured_resume,
                resume_path=resume_path,
                file_hash=file_hash,
                embedding=embedding,
                applicant_id=applicant_id,
            )
            logger.info(
                f"Resume Processed Successfully : {resume_url}"
            )
            return file_hash
        except ValueError as e:
            logger.warning(
                str(e)
            )
            return "DUPLICATE"
        except Exception as e:
            logger.exception(e)
            return ""
        finally:
            self._cleanup(
                local_resume
            )

    def _download_resume(
        self,
        resume_url: str,
    ) -> str:

        logger.info(f"Downloading Resume : {resume_url}")

        response = requests.get(
            resume_url,
            timeout=120,
        )
        response.raise_for_status()

        extension = os.path.splitext(
            resume_url.split("?")[0]
        )[1]

        if not extension:
            extension = ".pdf"

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        )

        temp_file.write(response.content)
        temp_file.close()

        logger.info(f"Downloaded : {temp_file.name}")

        return Path(temp_file.name)

    # Parse Resume
    def _parse_resume(
        self,
        resume_path: Path,
    ) -> dict:
        """
        Parse PDF/DOCX resume into text.
        """
        logger.info(
            "Parsing resume..."
        )
        parsed_resume = self.parser_service.parse_resume(
            resume_path
        )
        logger.info(
            "Resume parsed successfully."
        )
        return parsed_resume

    # Duplicate Validation
    def _check_duplicate(
        self,
        file_hash: str,
    ):
        """
        Validate duplicate resume.
        Raises ValueError if duplicate exists.
        """
        logger.info(
            "Checking duplicate..."
        )
        self.duplicate_service.validate(
            file_hash
        )
        logger.info(
            "Duplicate check completed."
        )

    # Resume Extraction
    def _extract_resume(
        self,
        raw_text: str,
    ) -> dict:
        """
        Extract structured information
        using Gemini.
        """
        logger.info(
            "Extracting structured resume..."
        )
        resume = self.resume_extractor.extract_resume(
            raw_text
        )
        logger.info(
            "Resume extracted."
        )
        return resume
    
    # Generate Embedding
    def _generate_embedding(
        self,
        resume: dict,
    ) -> list:
        """
        Generate embedding for the structured resume.
        """
        logger.info(
            "Preparing embedding text..."
        )
        embedding_text = self.resume_extractor.build_embedding_text(
            resume
        )
        logger.info(
            "Generating embedding..."
        )
        embedding = self.embedding_service.generate_embedding(
            embedding_text
        )
        logger.info("Embedding generated.")
        return embedding

    # Save Candidate Profile
    def _save_profile(
        self,
        resume,
        resume_path,
        file_hash,
        embedding,
        applicant_id,
    ):
        return self.profile_repository.save_profile(
            resume=resume,
            resume_path=resume_path,
            file_hash=file_hash,
            embedding=embedding,
            applicant_id=applicant_id,
        )
        

    
    # Cleanup Temporary File
    def _cleanup(
        self,
        local_resume: Path | None,
    ):

        if local_resume is None:
            return

        try:

            if local_resume.exists():

                local_resume.unlink()

                logger.info(
                    f"Temporary file deleted : {local_resume.name}"
                )

            pdf_resume = local_resume.with_suffix(".pdf")

            if pdf_resume.exists():

                pdf_resume.unlink()

                logger.info(
                    f"Temporary file deleted : {pdf_resume.name}"
                )

        except Exception as e:

            logger.exception(e)