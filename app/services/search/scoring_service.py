from app.config.settings import settings
import math
import re
from app.config.logging import logger



class ScoringService:

    def __init__(self):
        # Final ATS Weight Distribution
        self.required_skill_weight = 35
        self.preferred_skill_weight = 5
        self.experience_weight = 20
        self.education_weight = 10
        self.certification_weight = 5
        self.job_title_weight = 10
        self.rerank_weight = 15

    # Skill Normalization
    def normalize_skill(
        self,
        skill: str,
    ) -> str:
        if not skill:
            return ""
        skill = skill.lower().strip()
        return re.sub(
            r"[\s\-_\.]+",
            "",
            skill,
        )
    
    # Education Ranking
    def education_rank(
        self,
        education,
    ) -> int:

        # Support new OpenAI education object
        if isinstance(education, dict):
            education = (
                education.get("value")
                or ""
            )

        education = str(
            education or ""
        ).lower().strip()

        if not education:
            return 0

        if "phd" in education:
            return 5

        if "doctorate" in education:
            return 5

        if "m.tech" in education:
            return 4

        if "mtech" in education:
            return 4

        if "master" in education:
            return 4

        if "mba" in education:
            return 4

        if "b.tech" in education:
            return 3

        if "btech" in education:
            return 3

        if "b.e" in education:
            return 3

        if "be " in education:
            return 3

        if "bachelor" in education:
            return 3

        if "diploma" in education:
            return 2

        if "intermediate" in education:
            return 1

        return 0

    # existing ranking logic below
    @staticmethod
    def normalize_education(
        value,
    ):
        if not value:
            return ""

        value = str(
            value
        ).lower().strip()

        return re.sub(
            r"[^a-z0-9]",
            "",
            value,
        )
    # Education Score

    def education_score(
        self,
        required,
        candidate,
    ):

        # --------------------------------------------------
        # Extract required education
        # --------------------------------------------------

        if isinstance(
            required,
            dict,
        ):

            required_value = (
                required.get(
                    "value"
                )
                or ""
            )

            required_search_terms = (
                required.get(
                    "search_terms"
                )
                or []
            )

        else:

            required_value = str(
                required
                or ""
            )

            required_search_terms = []

        # --------------------------------------------------
        # Add canonical value
        # --------------------------------------------------

        required_search_terms = list(
            required_search_terms
        )

        if (
            required_value
            and required_value
            not in required_search_terms
        ):
            required_search_terms.append(
                required_value
            )

        # --------------------------------------------------
        # No education requirement
        # --------------------------------------------------

        if not required_search_terms:

            return (
                0,
                False,
            )

        # --------------------------------------------------
        # Normalize candidate education
        # --------------------------------------------------

        if isinstance(
            candidate,
            list,
        ):

            education_parts = []

            for education in candidate:

                if isinstance(
                    education,
                    dict,
                ):

                    education_parts.extend(
                        [
                            str(
                                education.get(
                                    "degree",
                                    "",
                                )
                                or ""
                            ),
                            str(
                                education.get(
                                    "specialization",
                                    "",
                                )
                                or ""
                            ),
                            str(
                                education.get(
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
                            education
                            or ""
                        )
                    )

            candidate_text = " ".join(
                education_parts
            )

        elif isinstance(
            candidate,
            dict,
        ):

            candidate_text = " ".join(
                str(
                    value
                    or ""
                )
                for value in candidate.values()
            )

        else:

            candidate_text = str(
                candidate
                or ""
            )

        candidate_normalized = (
            self.normalize_education(
                candidate_text
            )
        )

        # --------------------------------------------------
        # No candidate education
        # --------------------------------------------------

        if not candidate_normalized:

            return (
                0,
                False,
            )

        # --------------------------------------------------
        # Match education
        # --------------------------------------------------

        for term in required_search_terms:

            if not term:
                continue

            normalized_term = (
                self.normalize_education(
                    term
                )
            )

            if not normalized_term:
                continue

            if (
                normalized_term
                in candidate_normalized
            ):

                return (
                    self.education_weight,
                    True,
                )

        # --------------------------------------------------
        # No match
        # --------------------------------------------------

        return (
            0,
            False,
        )
    # Certification Score

    def certification_score(
        self,
        required,
        candidate,
    ):
        """
        Calculate certification score.

        Supports both:
        - ["AWS Certified"]
        - [
            {
                "certification": "AWS Certified",
                "search_terms": [
                    "AWS",
                    "AWS Cloud Practitioner",
                    ...
                ]
            }
        ]
        """

        if not required:
            return (
                self.certification_weight,
                [],
            )

        candidate = [
            c.lower().strip()
            for c in candidate
            if c
        ]

        matched = []

        for cert in required:

            # ---------------------------------
            # Backward compatibility (string)
            # ---------------------------------
            if isinstance(cert, str):

                cert_name = cert.strip()

                if any(
                    cert_name.lower() in c
                    for c in candidate
                ):
                    matched.append(cert_name)

                continue

            # ---------------------------------
            # New object format
            # ---------------------------------
            if not isinstance(cert, dict):
                continue

            cert_name = cert.get(
                "certification",
                "",
            ).strip()

            search_terms = cert.get(
                "search_terms",
                [],
            )

            found = False

            for term in search_terms:

                if not term:
                    continue

                term = term.lower().strip()

                if any(term in c for c in candidate):
                    found = True
                    break

            if found:
                matched.append(cert_name)

        percentage = (
            len(matched)
            / len(required)
        )

        score = (
            percentage
            * self.certification_weight
        )

        return (
            round(score, 2),
            matched,
        )
    # Job Title Score

    def job_title_score(
        self,
        required_title,
        candidate_title,
    ):

        if not required_title:

            return self.job_title_weight

        required = required_title.lower()

        candidate = candidate_title.lower()

        if required == candidate:

            return self.job_title_weight

        if required in candidate:

            return self.job_title_weight * 0.90

        if candidate in required:

            return self.job_title_weight * 0.85

        return 0
    
    # Required Skill Score

    def required_skill_score(
        self,
        required_skills: list,
        candidate_skills: list,
    ):

        if not required_skills:
            return (
                self.required_skill_weight,
                [],
                [],
            )

        candidate_skill_set = [
            self.normalize_skill(skill)
            for skill in candidate_skills
            if skill
        ]

        matched = []
        missing = []

        for required in required_skills:

            if not isinstance(required, dict):
                continue

            primary_skill = required.get("skill", "")

            search_terms = [
                self.normalize_skill(term)
                for term in required.get(
                    "search_terms",
                    []
                )
                if term
            ]

            found = False

            for term in search_terms:

                if any(
                    term in skill or skill in term
                    for skill in candidate_skill_set
                ):
                    found = True
                    break

            if found:
                matched.append(primary_skill)
            else:
                missing.append(primary_skill)

        ratio = len(matched) / max(
            len(required_skills),
            1,
        )

        score = ratio * self.required_skill_weight

        return (
            round(score, 2),
            matched,
            missing,
        )
    # Preferred Skill Bonus

    def preferred_skill_score(
        self,
        preferred_skills: list,
        candidate_skills: list,
    ):

        if not preferred_skills:
            return (
                0,
                [],
            )

        candidate_skill_set = {
            self.normalize_skill(skill)
            for skill in candidate_skills
        }

        matched = []

        for preferred in preferred_skills:

            # Backward compatibility
            if isinstance(preferred, str):

                if self.normalize_skill(preferred) in candidate_skill_set:
                    matched.append(preferred)

                continue

            if not isinstance(preferred, dict):
                continue

            primary_skill = preferred.get("skill", "")

            search_terms = preferred.get("search_terms", [])

            normalized_terms = {
                self.normalize_skill(term)
                for term in search_terms
                if term
            }

            found = False

            for term in normalized_terms:

                if any(
                    term in skill or skill in term
                    for skill in candidate_skill_set
                ):
                    found = True
                    break

            if found:
                matched.append(primary_skill)

        ratio = len(matched) / max(len(preferred_skills), 1)

        bonus = ratio * self.preferred_skill_weight

        return (
            round(bonus, 2),
            matched,
        )

    # Experience Score

    def experience_score(
        self,
        candidate_years: float,
        experience: dict,
    ):

        if not experience:
            return self.experience_weight

        minimum = experience.get("min")
        maximum = experience.get("max")
#
        # No requirement#

        if minimum is None and maximum is None:
            return self.experience_weight
#
        # Ideal Range#

        if minimum is not None and maximum is not None:

            if minimum <= candidate_years <= maximum:

                return self.experience_weight

#

            if candidate_years < minimum:

                gap = minimum - candidate_years

                penalty = min(
                    gap * 2,
                    self.experience_weight,
                )

                return round(
                    self.experience_weight - penalty,
                    2,
                )

#

            gap = candidate_years - maximum

            penalty = min(
                gap * 0.75,
                self.experience_weight * 0.50,
            )

            return round(
                self.experience_weight - penalty,
                2,
            )
#
        # Only Minimum#

        if minimum is not None:

            if candidate_years >= minimum:

                excess = candidate_years - minimum

                if excess <= 8:

                    return self.experience_weight

                penalty = min(
                    (excess-8)*0.50,
                    5,
                )

                return round(
                    self.experience_weight-penalty,
                    2,
                )

            gap = minimum-candidate_years

            penalty = min(
                gap*2,
                self.experience_weight,
            )

            return round(
                self.experience_weight-penalty,
                2,
            )
#
        # Only Maximum#

        if maximum is not None:

            if candidate_years <= maximum:

                return self.experience_weight

            gap = candidate_years-maximum

            penalty=min(
                gap,
                self.experience_weight,
            )

            return round(
                self.experience_weight-penalty,
                2,
            )

        return self.experience_weight

    # Cross Encoder Score

    def rerank_score(
        self,
        rerank: float,
    ):

        rerank=max(
            0,
            min(
                rerank,
                1,
            ),
        )

        return round(
            rerank
            * self.rerank_weight,
            2,
        )

    # Final ATS Score

    def calculate_score(
        self,
        *,
        job,
        candidate,
    ):

        required_skill_score,\
        matched_required,\
        missing_required = self.required_skill_score(
            job.get(
                "required_skills",
                [],
            ),
            candidate.get(
                "skills",
                [],
            ),
        )

        preferred_skill_score,\
        matched_preferred = self.preferred_skill_score(
            job.get(
                "preferred_skills",
                [],
            ),
            candidate.get(
                "skills",
                [],
            ),
        )

        experience_score = self.experience_score(
            float(
                candidate.get(
                    "experience_years",
                    0,
                )
            ),
            job.get(
                "experience",
                {},
            ),
        )

        candidate_education = candidate.get("education", [])

        if candidate_education:

            # New format -> list of dictionaries
            if isinstance(candidate_education[0], dict):

                education_text = " ".join(
                    filter(
                        None,
                        [
                            edu.get("degree", "")
                            for edu in candidate_education
                        ]
                        +
                        [
                            edu.get("specialization", "")
                            for edu in candidate_education
                        ]
                        +
                        [
                            edu.get("institution", "")
                            for edu in candidate_education
                        ]
                    )
                )

            # Old format -> list of strings
            else:

                education_text = " ".join(candidate_education)

        else:

            education_text = ""

        education_score, education_match = self.education_score(
            job.get("education", ""),
            education_text,
        )

        certification_score,\
        matched_certifications = self.certification_score(
            job.get(
                "certifications",
                [],
            ),
            candidate.get(
                "certifications",
                [],
            ),
        )

        title_score = self.job_title_score(
            job.get(
                "title",
                "",
            ),
            candidate.get(
                "job_position",
                "",
            ),
        )

        rerank = self.rerank_score(
            candidate.get(
                "rerank_score",
                0,
            ),
        )

        total = (
            required_skill_score
            + preferred_skill_score
            + experience_score
            + education_score
            + certification_score
            + title_score
            + rerank
        )

        total = min(
            round(total,2),
            100,
        )

        return {

            "final_score": total,

            "matched_skills": matched_required,

            "missing_skills": missing_required,

            "matched_preferred_skills": matched_preferred,

            "matched_certifications": matched_certifications,

            "education_match": education_match,

            "score_breakdown":{

                "required_skills":required_skill_score,

                "preferred_skills":preferred_skill_score,

                "experience":experience_score,

                "education":education_score,

                "certifications":certification_score,

                "job_title":title_score,

                "rerank":rerank,

            }

        }
    # Score Candidates
    def score_candidates(
        self,
        search_id: str,
        job: dict,
        candidates: list,
        page: int,
        page_size: int,
    ):

        logger.info("=" * 80)
        logger.info("CALCULATING ATS SCORES")
        logger.info("=" * 80)

        scored_candidates = []

        for candidate in candidates:

            result = self.calculate_score(
                job=job,
                candidate=candidate,
            )

            candidate["matched_skills"] = (
                result["matched_skills"]
            )

            candidate["missing_skills"] = (
                result["missing_skills"]
            )

            candidate["matched_preferred_skills"] = (
                result["matched_preferred_skills"]
            )

            candidate["matched_certifications"] = (
                result["matched_certifications"]
            )

            candidate["education_match"] = (
                result["education_match"]
            )

            candidate["score_breakdown"] = (
                result["score_breakdown"]
            )

            candidate["skill_match_percentage"] = round(
                (
                    len(result["matched_skills"])
                    /
                    max(
                        len(
                            job.get(
                                "required_skills",
                                [],
                            )
                        ),
                        1,
                    )
                ) * 100,
                2,
            )

            candidate["final_score"] = (
                result["final_score"]
            )

            scored_candidates.append(
                candidate
            )

        # --------------------------------------------------
        # Highest ATS first
        # --------------------------------------------------

        scored_candidates.sort(
            key=lambda x: (
                x["final_score"],
                x.get(
                    "rerank_score",
                    0,
                ),
                x.get(
                    "semantic_score",
                    0,
                ),
            ),
            reverse=True,
        )

        # --------------------------------------------------
        # Pagination
        # --------------------------------------------------

        total_candidates = len(
            scored_candidates
        )

        total_pages = (
            total_candidates
            + page_size
            - 1
        ) // page_size

        logger.info(
            "ATS Scoring Completed."
        )

        start = (page - 1) * page_size
        end = start + page_size

        return {
            "search_id": search_id,
            "candidates": scored_candidates[start:end],
            "total_candidates": total_candidates,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size,
        }


    def get_dynamic_weights(
        self,
        job: dict,
    ):

        weights = {

            "required_skills": 35,

            "preferred_skills": 5,

            "experience": 20,

            "education": 10,

            "certifications": 5,

            "job_title": 10,

            "rerank": 15,

        }

        title = job.get(
            "title",
            "",
        ).lower()

        experience = job.get(
            "experience",
            {},
        )

        minimum = experience.get("min")
####
        # Fresher Jobs####

        if minimum is not None and minimum <= 1:

            weights["education"] = 15

            weights["experience"] = 10

            weights["preferred_skills"] = 10
####
        # Senior Jobs####

        elif minimum is not None and minimum >= 8:

            weights["experience"] = 30

            weights["education"] = 5

            weights["preferred_skills"] = 3
####
        # AI Roles####

        if any(

            keyword in title

            for keyword in [

                "ai",

                "machine learning",

                "ml",

                "nlp",

                "llm",

                "genai",

            ]

        ):

            weights["required_skills"] = 40

            weights["experience"] = 18

            weights["rerank"] = 17
####
        # DevOps####

        if "devops" in title:

            weights["certifications"] = 10

            weights["required_skills"] = 32
####
        # Architects####

        if "architect" in title:

            weights["experience"] = 35

            weights["required_skills"] = 30

            weights["education"] = 5
####
        # Normalize to 100####

        total = sum(
            weights.values()
        )

        factor = 100 / total

        for key in weights:

            weights[key] = round(

                weights[key] * factor,

                2,

            )

        return weights

    # existing ranking logic below


    # Certification Score

    def certification_score(
        self,
        required,
        candidate,
    ):
        """
        Calculate certification score.

        Supports both:
        - ["AWS Certified"]
        - [
            {
                "certification": "AWS Certified",
                "search_terms": [
                    "AWS",
                    "AWS Cloud Practitioner",
                    ...
                ]
            }
        ]
        """

        if not required:
            return (
                self.certification_weight,
                [],
            )

        candidate = [
            c.lower().strip()
            for c in candidate
            if c
        ]

        matched = []

        for cert in required:

            # ---------------------------------
            # Backward compatibility (string)
            # ---------------------------------
            if isinstance(cert, str):

                cert_name = cert.strip()

                if any(
                    cert_name.lower() in c
                    for c in candidate
                ):
                    matched.append(cert_name)

                continue

            # ---------------------------------
            # New object format
            # ---------------------------------
            if not isinstance(cert, dict):
                continue

            cert_name = cert.get(
                "certification",
                "",
            ).strip()

            search_terms = cert.get(
                "search_terms",
                [],
            )

            found = False

            for term in search_terms:

                if not term:
                    continue

                term = term.lower().strip()

                if any(term in c for c in candidate):
                    found = True
                    break

            if found:
                matched.append(cert_name)

        percentage = (
            len(matched)
            / len(required)
        )

        score = (
            percentage
            * self.certification_weight
        )

        return (
            round(score, 2),
            matched,
        )
    # Job Title Score

    def job_title_score(
        self,
        required_title,
        candidate_title,
    ):

        if not required_title:

            return self.job_title_weight

        required = required_title.lower()

        candidate = candidate_title.lower()

        if required == candidate:

            return self.job_title_weight

        if required in candidate:

            return self.job_title_weight * 0.90

        if candidate in required:

            return self.job_title_weight * 0.85

        return 0
    
    # Required Skill Score

    def required_skill_score(
        self,
        required_skills: list,
        candidate_skills: list,
    ):

        if not required_skills:
            return (
                self.required_skill_weight,
                [],
                [],
            )

        candidate_skill_set = [
            self.normalize_skill(skill)
            for skill in candidate_skills
            if skill
        ]

        matched = []
        missing = []

        for required in required_skills:

            if not isinstance(required, dict):
                continue

            primary_skill = required.get("skill", "")

            search_terms = [
                self.normalize_skill(term)
                for term in required.get(
                    "search_terms",
                    []
                )
                if term
            ]

            found = False

            for term in search_terms:

                if any(
                    term in skill or skill in term
                    for skill in candidate_skill_set
                ):
                    found = True
                    break

            if found:
                matched.append(primary_skill)
            else:
                missing.append(primary_skill)

        ratio = len(matched) / max(
            len(required_skills),
            1,
        )

        score = ratio * self.required_skill_weight

        return (
            round(score, 2),
            matched,
            missing,
        )
    # Preferred Skill Bonus

    def preferred_skill_score(
        self,
        preferred_skills: list,
        candidate_skills: list,
    ):

        if not preferred_skills:
            return (
                0,
                [],
            )

        candidate_skill_set = {
            self.normalize_skill(skill)
            for skill in candidate_skills
        }

        matched = []

        for preferred in preferred_skills:

            # Backward compatibility
            if isinstance(preferred, str):

                if self.normalize_skill(preferred) in candidate_skill_set:
                    matched.append(preferred)

                continue

            if not isinstance(preferred, dict):
                continue

            primary_skill = preferred.get("skill", "")

            search_terms = preferred.get("search_terms", [])

            normalized_terms = {
                self.normalize_skill(term)
                for term in search_terms
                if term
            }

            found = False

            for term in normalized_terms:

                if any(
                    term in skill or skill in term
                    for skill in candidate_skill_set
                ):
                    found = True
                    break

            if found:
                matched.append(primary_skill)

        ratio = len(matched) / max(len(preferred_skills), 1)

        bonus = ratio * self.preferred_skill_weight

        return (
            round(bonus, 2),
            matched,
        )

    # Experience Score

    def experience_score(
        self,
        candidate_years: float,
        experience: dict,
    ):

        if not experience:
            return self.experience_weight

        minimum = experience.get("min")
        maximum = experience.get("max")
#
        # No requirement#

        if minimum is None and maximum is None:
            return self.experience_weight
#
        # Ideal Range#

        if minimum is not None and maximum is not None:

            if minimum <= candidate_years <= maximum:

                return self.experience_weight

#

            if candidate_years < minimum:

                gap = minimum - candidate_years

                penalty = min(
                    gap * 2,
                    self.experience_weight,
                )

                return round(
                    self.experience_weight - penalty,
                    2,
                )

#

            gap = candidate_years - maximum

            penalty = min(
                gap * 0.75,
                self.experience_weight * 0.50,
            )

            return round(
                self.experience_weight - penalty,
                2,
            )
#
        # Only Minimum#

        if minimum is not None:

            if candidate_years >= minimum:

                excess = candidate_years - minimum

                if excess <= 8:

                    return self.experience_weight

                penalty = min(
                    (excess-8)*0.50,
                    5,
                )

                return round(
                    self.experience_weight-penalty,
                    2,
                )

            gap = minimum-candidate_years

            penalty = min(
                gap*2,
                self.experience_weight,
            )

            return round(
                self.experience_weight-penalty,
                2,
            )
#
        # Only Maximum#

        if maximum is not None:

            if candidate_years <= maximum:

                return self.experience_weight

            gap = candidate_years-maximum

            penalty=min(
                gap,
                self.experience_weight,
            )

            return round(
                self.experience_weight-penalty,
                2,
            )

        return self.experience_weight

    # Cross Encoder Score

    def rerank_score(
        self,
        rerank: float,
    ):

        rerank=max(
            0,
            min(
                rerank,
                1,
            ),
        )

        return round(
            rerank
            * self.rerank_weight,
            2,
        )

    # Final ATS Score

    def calculate_score(
        self,
        *,
        job,
        candidate,
    ):

        required_skill_score,\
        matched_required,\
        missing_required = self.required_skill_score(
            job.get(
                "required_skills",
                [],
            ),
            candidate.get(
                "skills",
                [],
            ),
        )

        preferred_skill_score,\
        matched_preferred = self.preferred_skill_score(
            job.get(
                "preferred_skills",
                [],
            ),
            candidate.get(
                "skills",
                [],
            ),
        )

        experience_score = self.experience_score(
            float(
                candidate.get(
                    "experience_years",
                    0,
                )
            ),
            job.get(
                "experience",
                {},
            ),
        )

        candidate_education = candidate.get("education", [])

        if candidate_education:

            # New format -> list of dictionaries
            if isinstance(candidate_education[0], dict):

                education_text = " ".join(
                    filter(
                        None,
                        [
                            edu.get("degree", "")
                            for edu in candidate_education
                        ]
                        +
                        [
                            edu.get("specialization", "")
                            for edu in candidate_education
                        ]
                        +
                        [
                            edu.get("institution", "")
                            for edu in candidate_education
                        ]
                    )
                )

            # Old format -> list of strings
            else:

                education_text = " ".join(candidate_education)

        else:

            education_text = ""

        education_score, education_match = self.education_score(
            job.get("education", ""),
            education_text,
        )

        certification_score,\
        matched_certifications = self.certification_score(
            job.get(
                "certifications",
                [],
            ),
            candidate.get(
                "certifications",
                [],
            ),
        )

        title_score = self.job_title_score(
            job.get(
                "title",
                "",
            ),
            candidate.get(
                "job_position",
                "",
            ),
        )

        rerank = self.rerank_score(
            candidate.get(
                "rerank_score",
                0,
            ),
        )

        total = (
            required_skill_score
            + preferred_skill_score
            + experience_score
            + education_score
            + certification_score
            + title_score
            + rerank
        )

        total = min(
            round(total,2),
            100,
        )

        return {

            "final_score": total,

            "matched_skills": matched_required,

            "missing_skills": missing_required,

            "matched_preferred_skills": matched_preferred,

            "matched_certifications": matched_certifications,

            "education_match": education_match,

            "score_breakdown":{

                "required_skills":required_skill_score,

                "preferred_skills":preferred_skill_score,

                "experience":experience_score,

                "education":education_score,

                "certifications":certification_score,

                "job_title":title_score,

                "rerank":rerank,

            }

        }
    # # Score Candidates
    # def score_candidates(
    #     self,
    #     search_id: str,
    #     job: dict,
    #     candidates: list,
    #     page: int,
    #     page_size: int,
    # ):

    #     logger.info("=" * 80)
    #     logger.info("CALCULATING ATS SCORES")
    #     logger.info("=" * 80)

    #     scored_candidates = []

    #     for candidate in candidates:

    
    #         # ATS Scoring
    

    #         result = self.scoring_service.calculate_score(
    #             job=job,
    #             candidate=candidate,
    #         )

    #         candidate["matched_skills"] = result["matched_skills"]

    #         candidate["missing_skills"] = result["missing_skills"]

    #         candidate["matched_preferred_skills"] = result[
    #             "matched_preferred_skills"
    #         ]

    #         candidate["matched_certifications"] = result[
    #             "matched_certifications"
    #         ]

    #         candidate["education_match"] = result[
    #             "education_match"
    #         ]

    #         candidate["score_breakdown"] = result[
    #             "score_breakdown"
    #         ]

    #         candidate["skill_match_percentage"] = round(

    #             (
    #                 len(result["matched_skills"])
    #                 /
    #                 max(
    #                     len(
    #                         job.get(
    #                             "required_skills",
    #                             [],
    #                         )
    #                     ),
    #                     1,
    #                 )
    #             ) * 100,

    #             2,

    #         )

    #         candidate["final_score"] = result[
    #             "final_score"
    #         ]

    #         scored_candidates.append(candidate)


    #     # Highest ATS First


    #     scored_candidates.sort(

    #         key=lambda x: (

    #             x["final_score"],

    #             x.get(
    #                 "rerank_score",
    #                 0,
    #             ),

    #             x.get(
    #                 "semantic_score",
    #                 0,
    #             ),

    #         ),

    #         reverse=True,

    #     )


    #     # Pagination


    #     total_candidates = len(scored_candidates)

    #     total_pages = (

    #         total_candidates
    #         +
    #         page_size
    #         -
    #         1

    #     ) // page_size

    #     logger.info(
    #         "ATS Scoring Completed."
    #     )

    #     return self.generate_reasoning(

    #         search_id=search_id,

    #         candidates=scored_candidates,

    #         total_candidates=total_candidates,

    #         total_pages=total_pages,

    #         page=page,

    #         page_size=page_size,

    #     )


    def get_dynamic_weights(
        self,
        job: dict,
    ):

        weights = {

            "required_skills": 35,

            "preferred_skills": 5,

            "experience": 20,

            "education": 10,

            "certifications": 5,

            "job_title": 10,

            "rerank": 15,

        }

        title = job.get(
            "title",
            "",
        ).lower()

        experience = job.get(
            "experience",
            {},
        )

        minimum = experience.get("min")
####
        # Fresher Jobs####

        if minimum is not None and minimum <= 1:

            weights["education"] = 15

            weights["experience"] = 10

            weights["preferred_skills"] = 10
####
        # Senior Jobs####

        elif minimum is not None and minimum >= 8:

            weights["experience"] = 30

            weights["education"] = 5

            weights["preferred_skills"] = 3
####
        # AI Roles####

        if any(

            keyword in title

            for keyword in [

                "ai",

                "machine learning",

                "ml",

                "nlp",

                "llm",

                "genai",

            ]

        ):

            weights["required_skills"] = 40

            weights["experience"] = 18

            weights["rerank"] = 17
####
        # DevOps####

        if "devops" in title:

            weights["certifications"] = 10

            weights["required_skills"] = 32
####
        # Architects####

        if "architect" in title:

            weights["experience"] = 35

            weights["required_skills"] = 30

            weights["education"] = 5
####
        # Normalize to 100####

        total = sum(
            weights.values()
        )

        factor = 100 / total

        for key in weights:

            weights[key] = round(

                weights[key] * factor,

                2,

            )

        return weights

    # existing ranking logic below


    # Certification Score

    def certification_score(
        self,
        required,
        candidate,
    ):
        """
        Calculate certification score.

        Supports both:
        - ["AWS Certified"]
        - [
            {
                "certification": "AWS Certified",
                "search_terms": [
                    "AWS",
                    "AWS Cloud Practitioner",
                    ...
                ]
            }
        ]
        """

        if not required:
            return (
                self.certification_weight,
                [],
            )

        candidate = [
            c.lower().strip()
            for c in candidate
            if c
        ]

        matched = []

        for cert in required:

            # ---------------------------------
            # Backward compatibility (string)
            # ---------------------------------
            if isinstance(cert, str):

                cert_name = cert.strip()

                if any(
                    cert_name.lower() in c
                    for c in candidate
                ):
                    matched.append(cert_name)

                continue

            # ---------------------------------
            # New object format
            # ---------------------------------
            if not isinstance(cert, dict):
                continue

            cert_name = cert.get(
                "certification",
                "",
            ).strip()

            search_terms = cert.get(
                "search_terms",
                [],
            )

            found = False

            for term in search_terms:

                if not term:
                    continue

                term = term.lower().strip()

                if any(term in c for c in candidate):
                    found = True
                    break

            if found:
                matched.append(cert_name)

        percentage = (
            len(matched)
            / len(required)
        )

        score = (
            percentage
            * self.certification_weight
        )

        return (
            round(score, 2),
            matched,
        )
    # Job Title Score

    def job_title_score(
        self,
        required_title,
        candidate_title,
    ):

        if not required_title:

            return self.job_title_weight

        required = required_title.lower()

        candidate = candidate_title.lower()

        if required == candidate:

            return self.job_title_weight

        if required in candidate:

            return self.job_title_weight * 0.90

        if candidate in required:

            return self.job_title_weight * 0.85

        return 0
    
    # Required Skill Score

    def required_skill_score(
        self,
        required_skills: list,
        candidate_skills: list,
    ):

        if not required_skills:
            return (
                self.required_skill_weight,
                [],
                [],
            )

        candidate_skill_set = [
            self.normalize_skill(skill)
            for skill in candidate_skills
            if skill
        ]

        matched = []
        missing = []

        for required in required_skills:

            if not isinstance(required, dict):
                continue

            primary_skill = required.get("skill", "")

            search_terms = [
                self.normalize_skill(term)
                for term in required.get(
                    "search_terms",
                    []
                )
                if term
            ]

            found = False

            for term in search_terms:

                if any(
                    term in skill or skill in term
                    for skill in candidate_skill_set
                ):
                    found = True
                    break

            if found:
                matched.append(primary_skill)
            else:
                missing.append(primary_skill)

        ratio = len(matched) / max(
            len(required_skills),
            1,
        )

        score = ratio * self.required_skill_weight

        return (
            round(score, 2),
            matched,
            missing,
        )
    # Preferred Skill Bonus

    def preferred_skill_score(
        self,
        preferred_skills: list,
        candidate_skills: list,
    ):

        if not preferred_skills:
            return (
                0,
                [],
            )

        candidate_skill_set = {
            self.normalize_skill(skill)
            for skill in candidate_skills
        }

        matched = []

        for preferred in preferred_skills:

            # Backward compatibility
            if isinstance(preferred, str):

                if self.normalize_skill(preferred) in candidate_skill_set:
                    matched.append(preferred)

                continue

            if not isinstance(preferred, dict):
                continue

            primary_skill = preferred.get("skill", "")

            search_terms = preferred.get("search_terms", [])

            normalized_terms = {
                self.normalize_skill(term)
                for term in search_terms
                if term
            }

            found = False

            for term in normalized_terms:

                if any(
                    term in skill or skill in term
                    for skill in candidate_skill_set
                ):
                    found = True
                    break

            if found:
                matched.append(primary_skill)

        ratio = len(matched) / max(len(preferred_skills), 1)

        bonus = ratio * self.preferred_skill_weight

        return (
            round(bonus, 2),
            matched,
        )

    # Experience Score

    def experience_score(
        self,
        candidate_years: float,
        experience: dict,
    ):

        if not experience:
            return self.experience_weight

        minimum = experience.get("min")
        maximum = experience.get("max")
#
        # No requirement#

        if minimum is None and maximum is None:
            return self.experience_weight
#
        # Ideal Range#

        if minimum is not None and maximum is not None:

            if minimum <= candidate_years <= maximum:

                return self.experience_weight

#

            if candidate_years < minimum:

                gap = minimum - candidate_years

                penalty = min(
                    gap * 2,
                    self.experience_weight,
                )

                return round(
                    self.experience_weight - penalty,
                    2,
                )

#

            gap = candidate_years - maximum

            penalty = min(
                gap * 0.75,
                self.experience_weight * 0.50,
            )

            return round(
                self.experience_weight - penalty,
                2,
            )
#
        # Only Minimum#

        if minimum is not None:

            if candidate_years >= minimum:

                excess = candidate_years - minimum

                if excess <= 8:

                    return self.experience_weight

                penalty = min(
                    (excess-8)*0.50,
                    5,
                )

                return round(
                    self.experience_weight-penalty,
                    2,
                )

            gap = minimum-candidate_years

            penalty = min(
                gap*2,
                self.experience_weight,
            )

            return round(
                self.experience_weight-penalty,
                2,
            )
#
        # Only Maximum#

        if maximum is not None:

            if candidate_years <= maximum:

                return self.experience_weight

            gap = candidate_years-maximum

            penalty=min(
                gap,
                self.experience_weight,
            )

            return round(
                self.experience_weight-penalty,
                2,
            )

        return self.experience_weight

    # Cross Encoder Score

    def rerank_score(
        self,
        rerank: float,
    ):

        rerank=max(
            0,
            min(
                rerank,
                1,
            ),
        )

        return round(
            rerank
            * self.rerank_weight,
            2,
        )

    # Final ATS Score

    def calculate_score(
        self,
        *,
        job,
        candidate,
    ):

        required_skill_score,\
        matched_required,\
        missing_required = self.required_skill_score(
            job.get(
                "required_skills",
                [],
            ),
            candidate.get(
                "skills",
                [],
            ),
        )

        preferred_skill_score,\
        matched_preferred = self.preferred_skill_score(
            job.get(
                "preferred_skills",
                [],
            ),
            candidate.get(
                "skills",
                [],
            ),
        )

        experience_score = self.experience_score(
            float(
                candidate.get(
                    "experience_years",
                    0,
                )
            ),
            job.get(
                "experience",
                {},
            ),
        )

        candidate_education = candidate.get("education", [])

        if candidate_education:

            # New format -> list of dictionaries
            if isinstance(candidate_education[0], dict):

                education_text = " ".join(
                    filter(
                        None,
                        [
                            edu.get("degree", "")
                            for edu in candidate_education
                        ]
                        +
                        [
                            edu.get("specialization", "")
                            for edu in candidate_education
                        ]
                        +
                        [
                            edu.get("institution", "")
                            for edu in candidate_education
                        ]
                    )
                )

            # Old format -> list of strings
            else:

                education_text = " ".join(candidate_education)

        else:

            education_text = ""

        education_score, education_match = self.education_score(
            job.get("education", ""),
            education_text,
        )

        certification_score,\
        matched_certifications = self.certification_score(
            job.get(
                "certifications",
                [],
            ),
            candidate.get(
                "certifications",
                [],
            ),
        )

        title_score = self.job_title_score(
            job.get(
                "title",
                "",
            ),
            candidate.get(
                "job_position",
                "",
            ),
        )

        rerank = self.rerank_score(
            candidate.get(
                "rerank_score",
                0,
            ),
        )

        total = (
            required_skill_score
            + preferred_skill_score
            + experience_score
            + education_score
            + certification_score
            + title_score
            + rerank
        )

        total = min(
            round(total,2),
            100,
        )

        return {

            "final_score": total,

            "matched_skills": matched_required,

            "missing_skills": missing_required,

            "matched_preferred_skills": matched_preferred,

            "matched_certifications": matched_certifications,

            "education_match": education_match,

            "score_breakdown":{

                "required_skills":required_skill_score,

                "preferred_skills":preferred_skill_score,

                "experience":experience_score,

                "education":education_score,

                "certifications":certification_score,

                "job_title":title_score,

                "rerank":rerank,

            }

        }
    # Score Candidates
    # def score_candidates(
    #     self,
    #     search_id: str,
    #     job: dict,
    #     candidates: list,
    #     page: int,
    #     page_size: int,
    # ):

    #     logger.info("=" * 80)
    #     logger.info("CALCULATING ATS SCORES")
    #     logger.info("=" * 80)

    #     scored_candidates = []

    #     for candidate in candidates:

    
    #         # ATS Scoring
    

    #         result = self.scoring_service.calculate_score(
    #             job=job,
    #             candidate=candidate,
    #         )

    #         candidate["matched_skills"] = result["matched_skills"]

    #         candidate["missing_skills"] = result["missing_skills"]

    #         candidate["matched_preferred_skills"] = result[
    #             "matched_preferred_skills"
    #         ]

    #         candidate["matched_certifications"] = result[
    #             "matched_certifications"
    #         ]

    #         candidate["education_match"] = result[
    #             "education_match"
    #         ]

    #         candidate["score_breakdown"] = result[
    #             "score_breakdown"
    #         ]

    #         candidate["skill_match_percentage"] = round(

    #             (
    #                 len(result["matched_skills"])
    #                 /
    #                 max(
    #                     len(
    #                         job.get(
    #                             "required_skills",
    #                             [],
    #                         )
    #                     ),
    #                     1,
    #                 )
    #             ) * 100,

    #             2,

    #         )

    #         candidate["final_score"] = result[
    #             "final_score"
    #         ]

    #         scored_candidates.append(candidate)


    #     # Highest ATS First


    #     scored_candidates.sort(

    #         key=lambda x: (

    #             x["final_score"],

    #             x.get(
    #                 "rerank_score",
    #                 0,
    #             ),

    #             x.get(
    #                 "semantic_score",
    #                 0,
    #             ),

    #         ),

    #         reverse=True,

    #     )


    #     # Pagination


    #     total_candidates = len(scored_candidates)

    #     total_pages = (

    #         total_candidates
    #         +
    #         page_size
    #         -
    #         1

    #     ) // page_size

    #     logger.info(
    #         "ATS Scoring Completed."
    #     )

    #     return self.generate_reasoning(

    #         search_id=search_id,

    #         candidates=scored_candidates,

    #         total_candidates=total_candidates,

    #         total_pages=total_pages,

    #         page=page,

    #         page_size=page_size,

    #     )


    def get_dynamic_weights(
        self,
        job: dict,
    ):

        weights = {

            "required_skills": 35,

            "preferred_skills": 5,

            "experience": 20,

            "education": 10,

            "certifications": 5,

            "job_title": 10,

            "rerank": 15,

        }

        title = job.get(
            "title",
            "",
        ).lower()

        experience = job.get(
            "experience",
            {},
        )

        minimum = experience.get("min")
####
        # Fresher Jobs####

        if minimum is not None and minimum <= 1:

            weights["education"] = 15

            weights["experience"] = 10

            weights["preferred_skills"] = 10
####
        # Senior Jobs####

        elif minimum is not None and minimum >= 8:

            weights["experience"] = 30

            weights["education"] = 5

            weights["preferred_skills"] = 3
####
        # AI Roles####

        if any(

            keyword in title

            for keyword in [

                "ai",

                "machine learning",

                "ml",

                "nlp",

                "llm",

                "genai",

            ]

        ):

            weights["required_skills"] = 40

            weights["experience"] = 18

            weights["rerank"] = 17
####
        # DevOps####

        if "devops" in title:

            weights["certifications"] = 10

            weights["required_skills"] = 32
####
        # Architects####

        if "architect" in title:

            weights["experience"] = 35

            weights["required_skills"] = 30

            weights["education"] = 5
####
        # Normalize to 100####

        total = sum(
            weights.values()
        )

        factor = 100 / total

        for key in weights:

            weights[key] = round(

                weights[key] * factor,

                2,

            )

        return weights