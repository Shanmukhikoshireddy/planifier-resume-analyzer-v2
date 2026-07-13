import uuid
from datetime import datetime
from pathlib import Path
from app.config.logging import logger
from app.config.settings import settings
from app.repository.minio_repository import MinioRepository
from app.repository.profile_repository import ProfileRepository
from app.repository.embedding_repository import EmbeddingRepository
from app.services.ingestion.parser_service import ParserService
from app.services.ingestion.embedding_service import EmbeddingService
from app.services.ingestion.duplicate_service import DuplicateService
from app.services.llm.resume_extractor_service import ResumeExtractorService
from app.utils.hash import generate_hash
from app.services.shared.pdf_converter_service import (
    PdfConverterService,
)
class ResumeProcessor:
    def __init__(self):
        self.minio_repository = MinioRepository()
        self.profile_repository = ProfileRepository()
        self.embedding_repository = EmbeddingRepository()
        self.parser_service = ParserService()
        self.embedding_service = EmbeddingService()
        self.duplicate_service = DuplicateService()
        self.resume_extractor = ResumeExtractorService()
        self.converter = PdfConverterService()



    # Process Resume
    def process_resume(
        self,
        object_path: str,
    ) -> str:
        logger.info(
            f"Processing Resume : {object_path}"
        )
        local_resume = None
        file_hash = ""
        try:

            # Generate Resume ID
            resume_id = str(
                uuid.uuid4()
            )

            # Download Resume
            local_resume = self._download_resume(
            object_path
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
            parts = Path(object_path).parts
            if len(parts) >= 2:
                job_position = parts[1]
            else:
                job_position = "Unknown"
            structured_resume["job_position"] = job_position
            logger.info(
                f"Job Position : {job_position}"
            )
            structured_resume["file_hash"] = file_hash
            structured_resume["raw_text"] = raw_text
            structured_resume["file_name"] = Path(
                object_path
            ).name
        
            # Generate Embedding
            embedding = self._generate_embedding(
                structured_resume
            )

            # Save Candidate Profile
            resume_path = object_path

            # DOCX uploaded
            if pdf_resume:

                resume_path = object_path.replace(
                    ".docx",
                    ".pdf",
                )

                with open(
                    pdf_resume,
                    "rb",
                ) as file:

                    self.minio_repository.upload_file(

                        object_name=resume_path,

                        data=file.read(),

                        content_type="application/pdf",

                    )

                self.minio_repository.delete_file(
                    object_path
                )

                logger.info(
                    f"Deleted original DOCX : {object_path}"
                )


                logger.info(
                    "PDF uploaded to MinIO."
                )
            self._save_profile(

                resume_id=resume_id,

                resume=structured_resume,

                resume_path=resume_path,

                file_hash=file_hash,

            )

            # Save Embedding
            self._save_embedding(
                resume_id=resume_id,
                embedding=embedding,
                job_position=structured_resume.get(
                    "job_position",
                    "Unknown",
                ),
            )
            logger.info(
                f"Resume Processed Successfully : {object_path}"
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

    # Download Resume From MinIO
    def _download_resume(
        self,
        object_path: str,
    ) -> Path:

        logger.info(
            "Downloading resume from MinIO..."
        )

        resume_bytes = self.minio_repository.download_file(
            object_path
        )

        temp_dir = Path(
            settings.TEMP_DIR
        )

        temp_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        local_resume = temp_dir / Path(
            object_path
        ).name

        with open(
            local_resume,
            "wb",
        ) as file:

            file.write(
                resume_bytes
            )

        logger.info(
            f"Resume downloaded : {local_resume.name}"
        )

        return local_resume

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
        resume_id: str,
        resume: dict,
        resume_path: str,
        file_hash: str,
    ):
        """
        Save candidate profile in MongoDB.
        """
        logger.info(
            "Saving candidate profile..."
        )
        self.profile_repository.save_profile(
            resume_id=resume_id,
            resume=resume,
            resume_path=resume_path,
            file_hash=file_hash,
        )
        logger.info(
            "Candidate profile saved."
        )

    # Save Embedding
    def _save_embedding(
        self,
        resume_id: str,
        embedding: list,
        job_position: str,
    ):
        """
        Save embedding into MongoDB Atlas.
        """
        logger.info(
            "Saving embedding..."
        )
        self.embedding_repository.save_embedding(
            resume_id=resume_id,
            embedding=embedding,
            embedding_model=settings.EMBEDDING_MODEL,
            dimension=len(embedding),
            job_position=job_position,
            uploaded_at=datetime.utcnow(),
        )
        logger.info(
            "Embedding saved."
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