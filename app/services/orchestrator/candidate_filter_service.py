from typing import List, Dict
import re


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

        filtered = candidates

        filtered = self.filter_by_experience(filtered, job)

        filtered = self.filter_by_job_title(filtered, job)

        filtered = self.filter_by_skills(filtered, job)

        filtered = self.filter_by_location(filtered, job)

        filtered = self.filter_by_education(filtered, job)

        filtered = self.filter_by_excluded_skills(filtered, job)

        return filtered


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

            # Minimum + Maximum
            if minimum is not None and maximum is not None:

                if (
                    minimum - self.EXPERIENCE_TOLERANCE
                    <= years
                    <= maximum + self.EXPERIENCE_TOLERANCE
                ):
                    results.append(candidate)

            # Only Minimum
            elif minimum is not None:

                if years >= minimum - self.EXPERIENCE_TOLERANCE:
                    results.append(candidate)

            # Only Maximum
            elif maximum is not None:

                if years <= maximum + self.EXPERIENCE_TOLERANCE:
                    results.append(candidate)

        return results if results else candidates

    def filter_by_job_title(self, candidates, job):

        title = job.get("title", "").lower().strip()

        if not title:
            return candidates

        results = []

        for c in candidates:

            designation = str(
                c.get("designation", "")
            ).lower()

            position = str(
                c.get("job_position", "")
            ).lower()

            if title in designation or title in position:
                results.append(c)

        return results if results else candidates
    

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

        return results if results else candidates


    def filter_by_location(self, candidates, job):

        location = job.get("location", "")

        if not location:
            return candidates

        location = location.lower()

        results = [
            c
            for c in candidates
            if location in str(
                c.get("location", "")
            ).lower()
        ]

        return results if results else candidates


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

        return results if results else candidates


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

        return results if results else candidates
