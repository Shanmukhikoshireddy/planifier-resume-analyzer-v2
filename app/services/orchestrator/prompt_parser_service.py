from app.config.logging import logger
from app.services.shared.openai_service import OpenAIService
from app.prompts.intent_prompt import build_intent_prompt
from app.prompts.job_prompt import (
    build_job_prompt,
    build_modification_prompt,
)
class PromptParserService:

    def __init__(self):
        self.openai_service = OpenAIService()

    def detect_intent(self, prompt: str):

        logger.info("=" * 80)
        logger.info("INTENT DETECTION")
        logger.info("=" * 80)

        llm_prompt = build_intent_prompt(prompt)

        response = self.openai_service.generate_json(
            llm_prompt
        )
        logger.info(
            "Intent Response: %s",
            response,
        )

        if not isinstance(response, dict):
            raise ValueError("Invalid JSON returned.")

        intent = str(
            response.get("intent", "")
        ).strip().upper()

        valid_intents = {
            "SEARCH",
            "SEARCH_MODIFICATION",
            "GENERAL",
            "SHORTLIST",
            "REJECT",
            "SHOW_SHORTLISTED",
            "SHOW_REJECTED",
            "UNDO_SHORTLIST",
            "UNDO_REJECT",
            "CANDIDATE_REASONING",
            "SEARCH_HISTORY",
            "RESET_SEARCH",
        }

        if intent not in valid_intents:
            raise ValueError(f"Invalid intent : {intent}")

        response["intent"] = intent

        return response


    def parse_search(self, prompt: str):

        logger.info("=" * 80)
        logger.info("SEARCH PARSER")
        logger.info("=" * 80)
        llm_prompt = build_job_prompt(prompt)

        response = self.openai_service.generate_json(
            llm_prompt
        )

        logger.info(
            "RAW SEARCH RESPONSE TYPE: %s",
            type(response).__name__,
        )

        logger.info(
            "RAW SEARCH RESPONSE: %r",
            response,
        )

        if response is None:
            raise ValueError(
                "OpenAI returned an empty response."
            )

        if not isinstance(response, dict):
            raise ValueError(
                "Invalid JSON returned."
            )

        job = response.get("job")

        if not isinstance(job, dict):
            logger.error(
                f"Missing 'job' in search response: {response}"
            )
            raise ValueError(
                "Job object missing."
            )

        self._normalize(job)

        logger.info(
            f"Parsed Search Job:{job}"
        )

        return {
            "job": job
        }

    def parse(self, prompt: str) -> dict:
        """
        Parse a natural language prompt into a structured request.
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

        response = self.openai_service.generate_json(
            llm_prompt
        )
        logger.info(
            "RAW MODIFICATION RESPONSE: %s",
            response,
        )

        logger.info("OpenAI Response:")
        logger.info(response)

        if not isinstance(response, dict):
            raise ValueError(
                "OpenAI did not return a valid JSON object."
            )

        intent = str(response.get("intent", "")).strip().upper()

        valid_intents = {
            "SEARCH",
            "GENERAL",
            "SHORTLIST",
            "REJECT",
            "SHOW_SHORTLISTED",
            "SHOW_REJECTED",
            "UNDO_SHORTLIST",
            "UNDO_REJECT",
            "SEARCH_MODIFICATION",
            "SEARCH_HISTORY",
            "COMPARE_CANDIDATES",
            "CANDIDATE_REASONING",
            "RESET_SEARCH",
        }

        logger.info(
            "Intent after normalization: '%s'",
            intent,
        )

        logger.info(
            "Valid? %s",
            intent in valid_intents,
        )

        if intent not in valid_intents:
            raise ValueError(
                f"OpenAI returned invalid intent: '{intent}'"
            )

        response["intent"] = intent

        ####################################################
        # GENERAL
        ####################################################

        if intent == "GENERAL":

            return {
                "intent": "GENERAL"
            }

        ####################################################
        # Candidate Actions
        ####################################################

        if intent in [
            "SHORTLIST",
            "REJECT",
            "UNDO_SHORTLIST",
            "UNDO_REJECT",
        ]:

            candidate_name = response.get(
                "candidate_name",
                "",
            )  

            if not candidate_name:

                raise ValueError(
                    "Candidate name is required."
                )

            return {

                "intent": intent,

                "candidate_name": candidate_name,

            }

        ####################################################
        # Show Candidate Lists
        ####################################################

        if intent in [

            "SHOW_SHORTLISTED",

            "SHOW_REJECTED",

        ]:

            return {

                "intent": intent,

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

            "job": job,

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
                "min_operator": None,
                "max_operator": None,
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
        job["experience"].setdefault("min_operator", None)
        job["experience"].setdefault("max_operator", None)

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

    def parse_modification(self, prompt: str):

        logger.info("=" * 80)
        logger.info("MODIFICATION PARSER")
        logger.info("=" * 80)

        llm_prompt = build_modification_prompt(prompt)

        response = self.openai_service.generate_json(
            llm_prompt
        )
        logger.info(
            "RAW MODIFICATION RESPONSE: %s",
            response,
        )

        if not isinstance(response, dict):
            raise ValueError("Invalid JSON returned.")

        job = response.get("job")

        if not isinstance(job, dict):
            raise ValueError("Modification job object missing.")

        self._normalize(job)

        logger.info("Parsed Modification:")
        logger.info(job)

        return {
            "job": job
        }