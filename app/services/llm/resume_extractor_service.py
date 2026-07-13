import json
from app.config.logging import logger
from app.services.shared.openai_service import OpenAIService
from app.prompts.resume_prompt import build_resume_prompt
class ResumeExtractorService:
    """
    Responsible for extracting structured resume data
    from raw resume text using Gemini.
    """
    def __init__(self):
        self.llm = OpenAIService()

    # Extract Resume
    def extract_resume(
        self,
        raw_text: str,
    ) -> dict:
        logger.info(
            "Extracting structured resume..."
        )
        prompt = build_resume_prompt(
            raw_text
        )

        resume = self.llm.generate_json(
            prompt
        )
        resume = self._validate_resume(
            resume
        )
        logger.info(
            "Resume extracted successfully."
        )
        return resume
    
    # Validate Resume
    def _validate_resume(
        self,
        resume: dict,
    ) -> dict:
        defaults = {
            "candidate_name": "",
            "email": "",
            "phone": "",
            "location": "",
            "summary": "",
            "experience_years": 0,
            "skills": [],
            "education": [],
            "projects": [],
            "certifications": [],
            "designation": "",
            "job_position": "",
            "current_company": "",
        }
        for key, value in defaults.items():
            if key not in resume:
                resume[key] = value
        return resume

    # Resume Text for Embedding
    def build_embedding_text(
        self,
        resume: dict,
    ) -> str:

        parts = []

        for key in [
            "summary",
            "skills",
            "education",
            "projects",
            "certifications",
        ]:

            value = resume.get(key)

            if not value:
                continue

            if isinstance(value, str):

                parts.append(value)

            elif isinstance(value, list):

                for item in value:

                    if isinstance(item, str):

                        parts.append(item)

                    elif isinstance(item, dict):

                        parts.append(
                            json.dumps(
                                item,
                                ensure_ascii=False,
                            )
                        )

            elif isinstance(value, dict):

                parts.append(
                    json.dumps(
                        value,
                        ensure_ascii=False,
                    )
                )

        return "\n".join(parts)