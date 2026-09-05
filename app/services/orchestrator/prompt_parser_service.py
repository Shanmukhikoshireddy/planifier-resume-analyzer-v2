from app.config.logging import logger
from app.services.shared.openai_service import OpenAIService
from app.prompts.intent_prompt import build_intent_prompt
from app.prompts.job_prompt import (
    build_job_prompt,
    build_modification_prompt,
)
import re


_ACTION_INTENT = re.compile(
    r"\b(shortlist|shortlisted|unshortlist|reject|rejected|undo|reason|reasoning|why|explain|history|reset|"
    r"show shortlisted|show rejected)\b",
    re.IGNORECASE,
)
_SEARCH_INTENT = re.compile(
    r"\b(find|search|get|show|need|looking|candidates?|profiles?|"
    r"developer|engineer|years?|skill|experience|location|hyderabad|bangalore|pune|mumbai|delhi|chennai|noida|gurgaon|hitech)\b",
    re.IGNORECASE,
)


class PromptParserService:

    def __init__(self):
        self.openai_service = OpenAIService()

    def detect_intent(self, prompt: str):

        logger.info("=" * 80)
        logger.info("INTENT DETECTION")
        logger.info("=" * 80)

        # Fast action intent detection
        if prompt:
            prompt_lower = prompt.lower().strip()
            prompt_clean = re.sub(r"[.,?!:;]+$", "", prompt_lower).strip()

            # Fast SHOW_SHORTLISTED
            if re.search(r"\b(?:show|get|give|want|list|view|see)?\s*(?:all\s+)?(?:candidates?\s+)?(?:who\s+are\s+)?shortlisted\b", prompt_clean):
                job_match = re.search(
                    r"shortlisted\s+(?:candidates?\s+)?(?:for|in|as|under)\s+([a-zA-Z0-9_\s\-/]+)",
                    prompt_clean,
                )
                job_pos = job_match.group(1).strip() if job_match else ""
                job_pos = re.sub(r"\s+(?:candidates?|profiles?)$", "", job_pos).strip()
                logger.info(f"Fast intent: SHOW_SHORTLISTED (job_position={job_pos})")
                return {"intent": "SHOW_SHORTLISTED", "job_position": job_pos}

            # Fast SHOW_REJECTED
            if re.search(r"\b(?:show|get|give|want|list|view|see)?\s*(?:all\s+)?(?:candidates?\s+)?(?:who\s+are\s+)?rejected\b", prompt_clean):
                job_match = re.search(
                    r"rejected\s+(?:candidates?\s+)?(?:for|in|as|under)\s+([a-zA-Z0-9_\s\-/]+)",
                    prompt_clean,
                )
                job_pos = job_match.group(1).strip() if job_match else ""
                job_pos = re.sub(r"\s+(?:candidates?|profiles?)$", "", job_pos).strip()
                logger.info(f"Fast intent: SHOW_REJECTED (job_position={job_pos})")
                return {"intent": "SHOW_REJECTED", "job_position": job_pos}

            # Fast SHOW_CANDIDATES
            show_candidates_patterns = [
                r"^(?:show|give|display|list|view|get|see)\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?candidates?(?:\s+list)?$",
                r"^i\s+want\s+(?:all\s+)?(?:the\s+)?candidates?(?:\s+list)?$",
                r"^(?:all\s+)?candidates?(?:\s+list)?$",
                r"^show\s+current\s+candidates?$",
                r"^(?:what|which)\s+(?:are\s+the\s+)?candidates?(?:\s+list)?$",
            ]
            if any(re.search(pat, prompt_clean) for pat in show_candidates_patterns):
                logger.info("Fast intent: SHOW_CANDIDATES")
                return {"intent": "SHOW_CANDIDATES"}

            # Fast CANDIDATE_REASONING (pronouns / generic)
            reasoning_pronoun_pattern = (
                r"\bwhy\s+(?:is\s+|was\s+|did\s+you\s+select\s+)?(?:he|him|she|they|this\s+candidate|the\s+candidate)?\s*"
                r"(?:selected|shortlisted|chosen|recommended|ranked|a\s+good\s+(?:match|fit))\b"
            )
            if re.search(reasoning_pronoun_pattern, prompt_clean):
                logger.info("Fast intent: CANDIDATE_REASONING (pronoun/generic)")
                return {"intent": "CANDIDATE_REASONING", "candidate_name": ""}

            # Fast CANDIDATE_REASONING (named candidate)
            reasoning_named_match = re.search(
                r"\bwhy\s+(?:is\s+|was\s+)?([a-zA-Z\s]+?)\s+(?:selected|shortlisted|chosen|recommended|ranked|a\s+good\s+(?:match|fit))\b",
                prompt_clean,
            )
            if reasoning_named_match:
                extracted_name = reasoning_named_match.group(1).strip()
                extracted_name = re.sub(r"^(?:is|was)\s+", "", extracted_name).strip()
                if extracted_name.lower() in ("he", "him", "she", "they", "this candidate", "the candidate"):
                    extracted_name = ""
                logger.info(f"Fast intent: CANDIDATE_REASONING (candidate_name={extracted_name})")
                return {"intent": "CANDIDATE_REASONING", "candidate_name": extracted_name}

            # Fast simple reasoning queries like "why rahul", "explain alex"
            simple_reasoning_match = re.search(
                r"^(?:why|explain|reason\s+for)\s+([a-zA-Z]+)(?:\s+(?:profile|candidate))?\??$",
                prompt_clean,
            )
            if simple_reasoning_match:
                extracted_name = simple_reasoning_match.group(1).strip()
                if extracted_name.lower() not in ("he", "him", "she", "they", "this", "that", "it"):
                    logger.info(f"Fast intent: CANDIDATE_REASONING (candidate_name={extracted_name})")
                    return {"intent": "CANDIDATE_REASONING", "candidate_name": extracted_name}

        if prompt and not _ACTION_INTENT.search(prompt) and _SEARCH_INTENT.search(prompt):
            logger.info("Fast intent: SEARCH")
            return {"intent": "SEARCH"}

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
            "SHOW_CANDIDATES",
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