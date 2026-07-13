from pathlib import Path
from pypdf import PdfReader
from docx import Document
from app.config.logging import logger

class ParserService:

    # Parse Resume
    def parse_resume(
        self,
        file_path: str | Path,
    ) -> dict:
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            raw_text = self.parse_pdf(
                file_path
            )
        elif suffix == ".docx":
            raw_text = self.parse_docx(
                file_path
            )
        else:
            raise ValueError(
                f"Unsupported file : {suffix}"
            )
        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "raw_text": raw_text,
        }

    # PDF Parser
    def parse_pdf(
        self,
        pdf_path: Path,
    ) -> str:
        logger.info(
            f"Reading PDF : {pdf_path.name}"
        )
        reader = PdfReader(
            str(pdf_path)
        )
        pages = []
        for page in reader.pages:
            pages.append(
                page.extract_text() or ""
            )
        return "\n".join(
            pages
        )

    # DOCX Parser
    def parse_docx(
        self,
        docx_path: Path,
    ) -> str:
        logger.info(
            f"Reading DOCX : {docx_path.name}"
        )
        document = Document(
            str(docx_path)
        )
        paragraphs = []
        for paragraph in document.paragraphs:
            paragraphs.append(
                paragraph.text
            )
        return "\n".join(
            paragraphs
        )

    # Batch Parser
    def parse_resumes(
        self,
        resume_paths: list,
    ) -> list:
        parsed = []
        for path in resume_paths:
            try:
                parsed.append(
                    self.parse_resume(
                        path
                    )
                )
            except Exception as e:
                logger.exception(e)
        return parsed