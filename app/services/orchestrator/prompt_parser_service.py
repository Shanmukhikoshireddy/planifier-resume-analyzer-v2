from app.config.logging import logger
from app.prompts.job_prompt import build_job_prompt
from app.services.shared.openai_service import OpenAIService


class PromptParserService:
    """
    Converts a natural language user prompt into a structured job JSON.

    Examples:
        "Need Python developer with FastAPI"
        "Find AI/ML candidates with 2 years experience"
        "Python developer in Hyderabad"

    Returns:
        {
            "title": "...",
            "experience": "...",
            "education": "...",
            "skills": [],
            "certifications": [],
            "responsibilities": [],
            "qualifications": [],
            "nice_to_have": []
        }
    """

    def __init__(self):
        self.openai_service = OpenAIService()

    def parse(self, prompt: str) -> dict:
        """
        Parse a natural language prompt into a structured job object.
        """

        logger.info("=" * 80)
        logger.info("PROMPT PARSER")
        logger.info("=" * 80)

        if not prompt:
            raise ValueError("Prompt cannot be empty.")

        logger.info("User Prompt:")
        logger.info(prompt)

        llm_prompt = build_job_prompt(prompt)

        logger.info("Sending prompt to OpenAI...")

        response = self.openai_service.generate_json(llm_prompt)

        logger.info("OpenAI Response:")
        logger.info(response)

        if not isinstance(response, dict):
            raise ValueError(
                "OpenAI did not return a valid JSON object."
            )

        intent = response.get("intent")

        if intent not in ["SEARCH", "GENERAL"]:
            raise ValueError(
                "OpenAI did not return a valid intent."
            )

        ####################################################
        # GENERAL QUESTION
        ####################################################

        if intent == "GENERAL":

            return {
                "intent": "GENERAL"
            }

        ####################################################
        # SEARCH
        ####################################################

        job = response.get("job")

        if not isinstance(job, dict):
            raise ValueError(
                "SEARCH intent requires a job object."
            )

        self._normalize(job)

        logger.info("Normalized Parsed Job:")
        logger.info(job)

        return {
            "intent": "SEARCH",
            "job": job
        }

    def _normalize(self, job: dict):
        """
        Normalize parsed hiring requirements.
        """

        defaults = {
            "title": "",
            "experience": {
                "min": None,
                "max": None,
            },
            "education": "",
            "location": "",
            "required_skills": [],
            "preferred_skills": [],
            "excluded_skills": [],
            "certifications": [],
            "responsibilities": [],
            "qualifications": [],
            "nice_to_have": [],
            "keywords": [],
        }

        for key, value in defaults.items():
            if key not in job:
                job[key] = value

        # ----------------------------
        # Normalize string fields
        # ----------------------------
        for key in [
            "title",
            "education",
            "location",
        ]:
            if job[key] is None:
                job[key] = ""

        # ----------------------------
        # Normalize experience
        # ----------------------------
        if not isinstance(job["experience"], dict):
            job["experience"] = {
                "min": None,
                "max": None,
            }

        job["experience"].setdefault("min", None)
        job["experience"].setdefault("max", None)

        # ----------------------------
        # Initialize list fields
        # ----------------------------
        for key in [
            "required_skills",
            "preferred_skills",
            "excluded_skills",
            "certifications",
            "responsibilities",
            "qualifications",
            "nice_to_have",
            "keywords",
        ]:
            if job[key] is None:
                job[key] = []

        # ======================================================
        # Normalize certifications
        # ======================================================
        normalized_certifications = []

        for cert in job["certifications"]:

            if isinstance(cert, str):
                normalized_certifications.append(
                    {
                        "certification": cert,
                        "search_terms": [cert],
                    }
                )
                continue

            if not isinstance(cert, dict):
                continue

            cert.setdefault("certification", "")
            cert.setdefault("search_terms", [])

            if cert["search_terms"] is None:
                cert["search_terms"] = []

            seen = set()
            unique_terms = []

            for term in cert["search_terms"]:

                if not term:
                    continue

                term = term.strip()

                if term.lower() not in seen:
                    seen.add(term.lower())
                    unique_terms.append(term)

            primary = cert["certification"].strip()

            if primary:

                unique_terms = [
                    t for t in unique_terms
                    if t.lower() != primary.lower()
                ]

                unique_terms.insert(0, primary)

            cert["search_terms"] = unique_terms

            normalized_certifications.append(cert)

        job["certifications"] = normalized_certifications

        # ======================================================
        # Normalize required skills
        # ======================================================
        normalized_required_skills = []

        for skill in job["required_skills"]:

            if isinstance(skill, str):
                normalized_required_skills.append(
                    {
                        "skill": skill,
                        "search_terms": [skill],
                    }
                )
                continue

            if not isinstance(skill, dict):
                continue

            skill.setdefault("skill", "")
            skill.setdefault("search_terms", [])

            if skill["search_terms"] is None:
                skill["search_terms"] = []

            seen = set()
            unique_terms = []

            for term in skill["search_terms"]:

                if not term:
                    continue

                term = term.strip()

                if term.lower() not in seen:
                    seen.add(term.lower())
                    unique_terms.append(term)

            primary_skill = skill["skill"].strip()

            if primary_skill:

                unique_terms = [
                    t for t in unique_terms
                    if t.lower() != primary_skill.lower()
                ]

                unique_terms.insert(0, primary_skill)

            skill["search_terms"] = unique_terms

            normalized_required_skills.append(skill)

        job["required_skills"] = normalized_required_skills

        return job