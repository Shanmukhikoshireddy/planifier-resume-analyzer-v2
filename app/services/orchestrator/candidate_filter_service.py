from typing import List, Dict
import re
from app.config.logging import logger


class CandidateFilterService:
    """
    Applies business-rule filtering before reranking.

    Vector Search
            ↓
    CandidateFilterService
            ↓
    CrossEncoder
    """

    EXPERIENCE_TOLERANCE = 1

    def filter(
        self,
        candidates: List[Dict],
        job: Dict,
    ) -> List[Dict]:

        logger.info(f"Initial candidates: {len(candidates)}")

        candidates = self.filter_by_experience(candidates, job)
        logger.info(f"After experience: {len(candidates)}")

        candidates = self.filter_by_job_title(candidates, job)
        logger.info(f"After title: {len(candidates)}")

        candidates = self.filter_by_skills(candidates, job)
        logger.info(f"After skills: {len(candidates)}")

        candidates = self.filter_by_location(candidates, job)
        logger.info(f"After location: {len(candidates)}")

        candidates = self.filter_by_education(candidates, job)
        logger.info(f"After education: {len(candidates)}")

        candidates = self.filter_by_excluded_skills(candidates, job)
        logger.info(f"After excluded skills: {len(candidates)}")

        return candidates


    def filter_by_experience(
        self,
        candidates,
        job,
    ):
        experience = job.get("experience", {})

        if not isinstance(experience, dict):
            return candidates

        minimum = experience.get("min")
        maximum = experience.get("max")

        if minimum is None and maximum is None:
            return candidates

        results = []
        for candidate in candidates:

            years = float(
                candidate.get(
                    "experience_years",
                    0,
                )
            )

            # Exact experience (e.g. 4 years)
            if minimum is not None and maximum is not None:
                if years == minimum:
                    results.append(candidate)

            # Minimum only (e.g. minimum 4 years / 4+ years)
            elif minimum is not None:
                if years >= minimum:
                    results.append(candidate)

            # Maximum only (e.g. less than 4 years)
            elif maximum is not None:
                if years <= maximum:
                    results.append(candidate)

        return results

    def filter_by_job_title(
        self,
        candidates,
        job,
    ):

        title = job.get("title", "").lower().strip()

        if not title:
            return candidates

        results = []

        for candidate in candidates:

            designation = str(
                candidate.get("designation", "")
            ).lower()

            position = str(
                candidate.get("job_position", "")
            ).lower()

            if title in designation or title in position:
                results.append(candidate)

        return results
    

    def normalize_skill(
        self,
        skill: str,
    ) -> str:

        if not skill:
            return ""

        return re.sub(
            r"[\s\-_\.]+",
            "",
            skill.lower().strip(),
        )

    def filter_by_skills(
        self,
        candidates,
        job,
    ):

        required_skills = job.get(
            "required_skills",
            [],
        )

        if not required_skills:
            return candidates

        results = []

        for candidate in candidates:

            candidate_skills = {
                self.normalize_skill(skill)
                for skill in candidate.get("skills", [])
            }

            matched_required = 0

            for required in required_skills:

                if not isinstance(required, dict):
                    continue

                search_terms = {
                    self.normalize_skill(term)
                    for term in required.get(
                        "search_terms",
                        []
                    )
                    if term
                }

                if candidate_skills.intersection(search_terms):
                    matched_required += 1

            if matched_required >= max(
                1,
                len(required_skills) // 2,
            ):
                results.append(candidate)

        return results


    def filter_by_location(
        self,
        candidates,
        job,
    ):

        location = job.get("location", "")

        if not location:
            return candidates

        location = location.lower()

        results = [
            candidate
            for candidate in candidates
            if location in str(
                candidate.get("location", "")
            ).lower()
        ]

        return results


    def filter_by_education(self, candidates, job):

        education = job.get("education", "")

        if not education:
            return candidates

        education = education.lower()

        results = []

        for c in candidates:

            edu = " ".join(
                c.get("education", [])
            ).lower()

            if education in edu:
                results.append(c)

        return results


    def filter_by_excluded_skills(
        self,
        candidates,
        job,
    ):

        excluded_skills = job.get(
            "excluded_skills",
            [],
        )

        if not excluded_skills:
            return candidates

        results = []

        for candidate in candidates:

            candidate_skills = {
                self.normalize_skill(skill)
                for skill in candidate.get("skills", [])
            }

            has_excluded_skill = False

            for excluded in excluded_skills:

                if not isinstance(excluded, dict):
                    continue

                search_terms = {
                    self.normalize_skill(term)
                    for term in excluded.get(
                        "search_terms",
                        []
                    )
                    if term
                }

                if candidate_skills.intersection(search_terms):
                    has_excluded_skill = True
                    break

            if not has_excluded_skill:
                results.append(candidate)

        return results 
