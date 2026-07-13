from pathlib import Path
from docx2pdf import convert

from app.config.logging import logger


class PdfConverterService:

    def convert_docx_to_pdf(
        self,
        docx_path: str,
    ) -> str:

        docx_path = Path(docx_path)

        pdf_path = docx_path.with_suffix(".pdf")

        logger.info(
            f"Converting {docx_path.name} -> {pdf_path.name}"
        )

        convert(
            str(docx_path),
            str(pdf_path),
        )

        logger.info(
            "PDF Conversion Successful."
        )

        return str(pdf_path)