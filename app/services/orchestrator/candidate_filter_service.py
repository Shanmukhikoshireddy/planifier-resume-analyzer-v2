from typing import Dict, List
import re

from app.config.logging import logger
from app.repository.applicant_repository import ApplicantRepository


class CandidateFilterService:
    """
    Applies hard business-rule filtering before reranking. 

    The important distinction is:

    - Vector search retrieves potentially relevant candidates.
    - Explicit experience/location/education/exclusion constraints are hard.
    - Role relevance is checked using title + skill evidence.
    - Specialized roles such as Film Director remain strict.
    - Technical roles such as Python Developer can match valid title
      variations and strong skill evidence.
    """

    SPECIALIZED_ROLE_ALIASES = {

        "film director": {
            "film director",
            "movie director",
            "cinema director",
            "motion picture director",
            "filmmaker",
            "film maker",
            "feature film director",
            "independent film director",
            "short film director",
        },

        "filmmaker": {
            "filmmaker",
            "film maker",
            "film director",
            "movie director",
            "cinema director",
        },

        "movie director": {
            "movie director",
            "film director",
            "filmmaker",
            "film maker",
        },
    }

    TECHNICAL_ROLE_SKILLS = {

        "python developer": {
            "python",
        },

        "python engineer": {
            "python",
        },

        "python programmer": {
            "python",
        },

        "java developer": {
            "java",
        },

        "java engineer": {
            "java",
        },

        "ai ml developer": {
            "python",
            "machine learning",
            "ml",
            "artificial intelligence",
            "ai",
            "tensorflow",
            "pytorch",
            "scikit learn",
            "sklearn",
        },

        "ai/ml developer": {
            "python",
            "machine learning",
            "ml",
            "artificial intelligence",
            "ai",
            "tensorflow",
            "pytorch",
            "scikit learn",
            "sklearn",
        },

        "ai ml engineer": {
            "python",
            "machine learning",
            "ml",
            "artificial intelligence",
            "ai",
            "tensorflow",
            "pytorch",
        },

        "machine learning engineer": {
            "machine learning",
            "ml",
            "python",
            "tensorflow",
            "pytorch",
            "scikit learn",
            "sklearn",
        },

        "machine learning developer": {
            "machine learning",
            "ml",
            "python",
            "tensorflow",
            "pytorch",
        },

        "ml engineer": {
            "machine learning",
            "ml",
            "python",
            "tensorflow",
            "pytorch",
        },

        "ml developer": {
            "machine learning",
            "ml",
            "python",
        },

        "ai engineer": {
            "artificial intelligence",
            "ai",
            "machine learning",
            "ml",
            "python",
            "tensorflow",
            "pytorch",
        },

        "ai developer": {
            "artificial intelligence",
            "ai",
            "machine learning",
            "ml",
            "python",
        },

    }

    def __init__(self):

        self.applicant_repository = ApplicantRepository()

    # ============================================================
    # MAIN FILTER
    # ============================================================

    def filter(
        self,
        candidates: List[Dict],
        job: Dict,
    ) -> List[Dict]:

        if not candidates:
            return []

        logger.info(
            f"Initial candidates: {len(candidates)}"
        )

        candidates = self.filter_by_applicant_status(candidates)

        logger.info(
            f"After applicant status: {len(candidates)}"
        )

        candidates = self.filter_by_experience(
            candidates,
            job,
        )

        logger.info(
            f"After experience: {len(candidates)}"
        )

        candidates = self.filter_by_relevance(
            candidates,
            job,
        )

        logger.info(
            f"After role/skill relevance:{len(candidates)}"
        )

        candidates = self.filter_by_location(
            candidates,
            job,
        )

        logger.info(
            f"After location:{len(candidates)}"
        )

        candidates = self.filter_by_education(
            candidates,
            job,
        )

        logger.info(
            f"After education:{len(candidates)}"
        )

        candidates = self.filter_by_excluded_skills(
            candidates,
            job,
        )

        logger.info(
            f"After excluded skills: {len(candidates)}"
        )

        return candidates

    # ============================================================
    # APPLICANT STATUS
    # ============================================================

    def filter_by_applicant_status(
        self,
        candidates,
    ):

        if not candidates:
            return []

        applicant_ids = list(
            {
                candidate.get("applicant_id")
                for candidate in candidates
                if candidate.get("applicant_id")
            }
        )

        if not applicant_ids:
            return candidates

        status_map = (
            self.applicant_repository
            .get_applicant_status_map(
                applicant_ids
            )
        )

        excluded_statuses = {
            "ONBOARDING",
            "OFFER_RELEASED",
            "NEGOTIATION",
            "JOINED",
        }

        results = []

        for candidate in candidates:

            applicant_id = candidate.get(
                "applicant_id"
            )

            status = status_map.get(
                applicant_id,
                "DRAFT",
            )

            if status in excluded_statuses:
                continue

            results.append(candidate)

        return results

    # ============================================================
    # EXPERIENCE
    # ============================================================

    def filter_by_experience(
        self,
        candidates,
        experience,
    ):

        if not experience:
            return candidates

        minimum = experience.get("min")
        maximum = experience.get("max")

        min_operator = experience.get(
            "min_operator"
        )

        max_operator = experience.get(
            "max_operator"
        )

        results = []

        for candidate in candidates:

            candidate_exp = candidate.get(
                "experience_years"
            )

            if candidate_exp is None:
                continue

            # Minimum condition
            if minimum is not None:

                if min_operator == ">":
                    if candidate_exp <= minimum:
                        continue

                elif min_operator == ">=":
                    if candidate_exp < minimum:
                        continue

            # Maximum condition
            if maximum is not None:

                if max_operator == "<":
                    if candidate_exp >= maximum:
                        continue

                elif max_operator == "<=":
                    if candidate_exp > maximum:
                        continue

            results.append(candidate)

        return results

    # ============================================================
    # RELEVANCE
    # ============================================================

    def filter_by_relevance(
        self,
        candidates,
        job,
    ):

        title = self.clean_text(
            job.get("title", "")
        )

        required_skills = (
            job.get("required_skills")
            or []
        )

        valid_required_skills = [
            skill
            for skill in required_skills
            if (
                isinstance(skill, dict)
                and self._skill_terms(skill)
            )
        ]

        if (
            not title
            and not valid_required_skills
        ):
            return candidates

        results = []

        for candidate in candidates:

            title_match = False
            skills_match = False

            if title:

                title_match = (
                    self.matches_job_title(
                        candidate,
                        title,
                    )
                )

            if valid_required_skills:

                skills_match = (
                    self.matches_all_required_skills(
                        candidate,
                        valid_required_skills,
                    )
                )

            # ----------------------------------------------------
            # Specialized role
            # ----------------------------------------------------

            if self.is_specialized_role(
                title
            ):

                relevant = title_match

            # ----------------------------------------------------
            # Explicit skills only
            # ----------------------------------------------------

            elif not title:

                relevant = skills_match

            # ----------------------------------------------------
            # Technical/general role + skills
            # ----------------------------------------------------

            elif valid_required_skills:
                relevant = skills_match

            # ----------------------------------------------------
            # Title-only search
            # ----------------------------------------------------

            else:

                relevant = title_match

            if relevant:
                results.append(candidate)

        if not results:

            logger.info(
                "No candidates satisfied explicit "
                "role/skill requirements."
            )

        return results

    # ============================================================
    # TITLE MATCHING
    # ============================================================

    def matches_job_title(
        self,
        candidate,
        required_title,
    ):

        required_title = self.clean_text(
            required_title
        )

        if not required_title:
            return False

        aliases = self.title_aliases(
            required_title
        )

        designation = self.clean_text(
            candidate.get(
                "designation",
                "",
            )
        )

        job_position = self.clean_text(
            candidate.get(
                "job_position",
                "",
            )
        )

        summary = self.clean_text(
            candidate.get(
                "summary",
                "",
            )
        )

        resume_text = self.clean_text(
            candidate.get(
                "resume_text",
                "",
            )
        )

        structured_text = " ".join(
            value
            for value in [
                designation,
                job_position,
            ]
            if value
        )

        for alias in aliases:

            if self.contains_phrase(
                structured_text,
                alias,
            ):
                return True

        # For non-specialized technical roles,
        # allow skill evidence to support the title.
        if not self.is_specialized_role(
            required_title
        ):

            if self.title_has_technical_skill_family(
                required_title,
                candidate,
            ):
                return True

        fallback_text = " ".join(
            value
            for value in [
                summary,
                resume_text,
            ]
            if value
        )

        for alias in aliases:

            if self.contains_phrase(
                fallback_text,
                alias,
            ):
                return True

        return False

    # ============================================================
    # TITLE ALIASES
    # ============================================================

    def title_aliases(
        self,
        title,
    ):

        title = self.clean_text(
            title
        )

        aliases = {
            title
        }

        aliases.update(
            self.SPECIALIZED_ROLE_ALIASES.get(
                title,
                set(),
            )
        )

        technical_aliases = {
            "python developer": {
                "python developer",
                "python engineer",
                "python programmer",
                "python software developer",
                "software engineer python",
            },

            "python engineer": {
                "python developer",
                "python engineer",
                "python programmer",
            },

            "java developer": {
                "java developer",
                "java engineer",
                "java software developer",
            },

            "ai ml developer": {
                "ai ml developer",
                "ai/ml developer",
                "ai ml engineer",
                "ai/ml engineer",
                "ai engineer",
                "ai developer",
                "machine learning engineer",
                "machine learning developer",
                "ml engineer",
                "ml developer",
            },

            "ai/ml developer": {
                "ai ml developer",
                "ai/ml developer",
                "ai ml engineer",
                "ai/ml engineer",
                "ai engineer",
                "machine learning engineer",
                "machine learning developer",
                "ml engineer",
                "ml developer",
            },

            "machine learning engineer": {
                "machine learning engineer",
                "machine learning developer",
                "ml engineer",
                "ml developer",
                "ai engineer",
                "ai/ml engineer",
            },

            "machine learning developer": {
                "machine learning engineer",
                "machine learning developer",
                "ml engineer",
                "ml developer",
                "ai developer",
            },

            "ai engineer": {
                "ai engineer",
                "ai developer",
                "ai ml engineer",
                "ai ml developer",
                "machine learning engineer",
                "ml engineer",
            },
        }

        aliases.update(
            technical_aliases.get(
                title,
                set(),
            )
        )

        return {
            alias
            for alias in aliases
            if alias
        }

    # ============================================================
    # TECHNICAL ROLE → SKILL EVIDENCE
    # ============================================================

    def title_has_technical_skill_family(
        self,
        title,
        candidate,
    ):

        title = self.clean_text(
            title
        )

        required_skill_family = (
            self.TECHNICAL_ROLE_SKILLS.get(
                title
            )
        )

        if not required_skill_family:
            return False

        candidate_skills = {
            self.normalize_skill(
                skill
            )
            for skill in (
                candidate.get("skills")
                or []
            )
            if skill
        }

        candidate_text = self.clean_text(
            " ".join(
                [
                    str(
                        candidate.get(
                            "summary",
                            "",
                        )
                    ),
                    str(
                        candidate.get(
                            "resume_text",
                            "",
                        )
                    ),
                ]
            )
        )

        matches = 0

        for required in required_skill_family:

            normalized_required = (
                self.normalize_skill(
                    required
                )
            )

            if (
                normalized_required
                in candidate_skills
            ):

                matches += 1
                continue

            if self.contains_normalized_phrase(
                candidate_text,
                normalized_required,
            ):

                matches += 1

        # Python Developer:
        # Python evidence is enough.

        if title in {
            "python developer",
            "python engineer",
            "python programmer",
        }:

            return matches >= 1

        # AI/ML:
        # Require at least two independent
        # signals so generic "AI" mentions
        # do not match unrelated profiles.

        if (
            "ai" in title
            or "ml" in title
            or "machine learning" in title
        ):

            return matches >= 2

        return matches >= 1

    # ============================================================
    # SKILLS
    # ============================================================

    def matches_all_required_skills(
        self,
        candidate,
        required_skills,
    ):

        candidate_skills = [
            self.normalize_skill(
                skill
            )
            for skill in (
                candidate.get("skills")
                or []
            )
            if skill
        ]

        candidate_text = self.clean_text(
            " ".join(
                [
                    str(
                        candidate.get(
                            "resume_text",
                            "",
                        )
                    ),
                    str(
                        candidate.get(
                            "summary",
                            "",
                        )
                    ),
                ]
            )
        )

        for required in required_skills:

            search_terms = {
                self.normalize_skill(
                    term
                )
                for term in self._skill_terms(
                    required
                )
                if term
            }

            if not search_terms:
                continue

            matched = False

            for required_term in search_terms:

                for candidate_skill in candidate_skills:

                    if self.skill_matches(
                        required_term,
                        candidate_skill,
                    ):

                        matched = True
                        break

                if matched:
                    break

            if not matched:

                for required_term in search_terms:

                    if self.contains_normalized_phrase(
                        candidate_text,
                        required_term,
                    ):

                        matched = True
                        break

            if not matched:
                return False

        return True

    def _skill_terms(
        self,
        required,
    ):

        terms = []

        primary = required.get(
            "skill",
            "",
        )

        if primary:
            terms.append(
                str(primary)
            )

        for term in (
            required.get(
                "search_terms",
                [],
            )
            or []
        ):

            if term:
                terms.append(
                    str(term)
                )

        seen = set()
        unique = []

        for term in terms:

            key = self.normalize_skill(
                term
            )

            if key and key not in seen:

                seen.add(key)
                unique.append(term)

        return unique

    def skill_matches(
        self,
        required_term,
        candidate_skill,
    ):

        if (
            not required_term
            or not candidate_skill
        ):
            return False

        if (
            required_term
            == candidate_skill
        ):
            return True

        if (
            " "
            in required_term
        ):

            return (
                required_term
                in candidate_skill
            )

        return (
            required_term
            == candidate_skill
        )

    # ============================================================
    # LOCATION
    # ============================================================

    def filter_by_location(
        self,
        candidates,
        job,
    ):

        location = self.clean_text(
            job.get(
                "location",
                "",
            )
        )

        if not location:
            return candidates

        results = []

        for candidate in candidates:

            candidate_location = self.clean_text(
                candidate.get(
                    "location",
                    "",
                )
            )

            if self.contains_phrase(
                candidate_location,
                location,
            ):

                results.append(
                    candidate
                )

        return results
    # --------------------------------------------------
    # Normalize education
    #
    # B.Tech  -> btech
    # B-Tech  -> btech
    # B Tech  -> btech
    # B.Tech. -> btech
    # MBA     -> mba
    # M.B.A   -> mba
    # --------------------------------------------------
    @staticmethod
    def normalize_education(
        value,
    ):

        if not value:
            return ""

        return re.sub(
            r"[^a-z0-9]",
            "",
            str(value).lower(),
        )

    # ============================================================
    # EDUCATION
    # ============================================================

    def filter_by_education(
        self,
        candidates,
        job,
    ):
        education = (
            job.get("education")
            or {}
        )

        logger.info(
            "Education requirement: %s",
            education,
        )

        # --------------------------------------------------
        # No education requirement
        # --------------------------------------------------

        if not education:
            return candidates

        # --------------------------------------------------
        # Extract OpenAI-generated search terms
        # --------------------------------------------------

        if isinstance(education, dict):

            search_terms = (
                education.get(
                    "search_terms",
                    [],
                )
                or []
            )

            value = (
                education.get(
                    "value",
                    "",
                )
                or ""
            )

            # Include canonical value
            if value and value not in search_terms:

                search_terms = list(
                    search_terms
                )

                search_terms.append(
                    value
                )

        else:

            # Backward compatibility
            search_terms = [
                str(education)
            ]

        # --------------------------------------------------
        # No usable education terms
        # --------------------------------------------------

        if not search_terms:

            logger.info(
                "No education search terms. "
                "Skipping education filter."
            )

            return candidates

        

        normalized_terms = [
            self.normalize_education(term)
            for term in search_terms
            if term
        ]

        normalized_terms = [
            term
            for term in normalized_terms
            if term
        ]

        logger.info(
            "Normalized education search terms: %s",
            normalized_terms,
        )

        # --------------------------------------------------
        # Filter candidates
        # --------------------------------------------------

        results = []

        for candidate in candidates:

            candidate_education = (
                candidate.get(
                    "education",
                    "",
                )
                or ""
            )

            # Candidate education can be:
            #
            # ["B-Tech in ECE from MDU"]
            #
            # or
            #
            # [{"degree": "B.Tech", ...}]
            #

            if isinstance(
                candidate_education,
                list,
            ):

                education_parts = []

                for item in candidate_education:

                    if isinstance(
                        item,
                        dict,
                    ):

                        education_parts.extend(
                            [
                                str(
                                    item.get(
                                        "degree",
                                        "",
                                    )
                                    or ""
                                ),
                                str(
                                    item.get(
                                        "specialization",
                                        "",
                                    )
                                    or ""
                                ),
                                str(
                                    item.get(
                                        "institution",
                                        "",
                                    )
                                    or ""
                                ),
                            ]
                        )

                    else:

                        education_parts.append(
                            str(
                                item
                                or ""
                            )
                        )

                candidate_education = " ".join(
                    education_parts
                )

            elif isinstance(
                candidate_education,
                dict,
            ):

                candidate_education = " ".join(
                    str(
                        value
                        or ""
                    )
                    for value in candidate_education.values()
                )

            else:

                candidate_education = str(
                    candidate_education
                )

            normalized_candidate = (
                self.normalize_education(
                    candidate_education
                )
            )

            if not normalized_candidate:

                logger.info(
                    "Candidate has no education."
                )

                continue

            # --------------------------------------------------
            # Match normalized OpenAI search terms
            # --------------------------------------------------

            matched = any(
                term in normalized_candidate
                for term in normalized_terms
            )

            if matched:

                logger.info(
                    "Education matched: %s",
                    candidate_education,
                )

                results.append(
                    candidate
                )

            else:

                logger.info(
                    "Education not matched: %s",
                    candidate_education,
                )

        return results

    # ============================================================
    # EXCLUDED SKILLS
    # ============================================================

    def filter_by_excluded_skills(
        self,
        candidates,
        job,
    ):

        excluded_skills = (
            job.get(
                "excluded_skills"
            )
            or []
        )

        if not excluded_skills:
            return candidates

        results = []

        for candidate in candidates:

            candidate_skills = {
                self.normalize_skill(
                    skill
                )
                for skill in (
                    candidate.get(
                        "skills"
                    )
                    or []
                )
                if skill
            }

            candidate_text = self.clean_text(
                candidate.get(
                    "resume_text",
                    "",
                )
            )

            excluded = False

            for item in excluded_skills:

                if isinstance(
                    item,
                    str,
                ):

                    terms = [
                        item
                    ]

                elif isinstance(
                    item,
                    dict,
                ):

                    terms = self._skill_terms(
                        item
                    )

                else:

                    terms = []

                for term in terms:

                    normalized = (
                        self.normalize_skill(
                            term
                        )
                    )

                    if not normalized:
                        continue

                    if (
                        normalized
                        in candidate_skills
                    ):

                        excluded = True
                        break

                    if self.contains_normalized_phrase(
                        candidate_text,
                        normalized,
                    ):

                        excluded = True
                        break

                if excluded:
                    break

            if not excluded:
                results.append(
                    candidate
                )

        return results

    # ============================================================
    # ROLE HELPERS
    # ============================================================

    def is_specialized_role(
        self,
        title,
    ):

        title = self.clean_text(
            title
        )

        return (
            title
            in self.SPECIALIZED_ROLE_ALIASES
        )

    # ============================================================
    # TEXT HELPERS
    # ============================================================

    @staticmethod
    def clean_text(
        value,
    ):

        if value is None:
            return ""

        value = str(
            value
        ).lower().strip()

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value

    def normalize_skill(
        self,
        skill,
    ):

        if not skill:
            return ""

        value = self.clean_text(
            skill
        )

        value = re.sub(
            r"[^a-z0-9+#]+",
            "",
            value,
        )

        return value

    def contains_phrase(
        self,
        text,
        phrase,
    ):

        text = self.clean_text(
            text
        )

        phrase = self.clean_text(
            phrase
        )

        if (
            not text
            or not phrase
        ):
            return False

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(phrase)
            + r"(?![a-z0-9])"
        )

        return (
            re.search(
                pattern,
                text,
            )
            is not None
        )

    def contains_normalized_phrase(
        self,
        text,
        normalized_phrase,
    ):

        if (
            not text
            or not normalized_phrase
        ):
            return False

        normalized_text = (
            self.normalize_skill(
                text
            )
        )

        return (
            normalized_phrase
            in normalized_text
        )