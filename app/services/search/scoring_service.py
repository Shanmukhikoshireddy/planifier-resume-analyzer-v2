from app.config.settings import settings
import re

class ScoringService:
    """
    Calculates the final ATS score for a candidate.
    """
    def __init__(self):
        self.semantic_weight = settings.SEMANTIC_WEIGHT
        self.skill_weight = settings.SKILL_WEIGHT
        self.rerank_weight = settings.RERANK_WEIGHT
        self.experience_weight = settings.EXPERIENCE_WEIGHT
        self.education_weight = settings.EDUCATION_WEIGHT
        self.certification_weight = settings.CERTIFICATION_WEIGHT

    # Semantic Score
    def semantic_score(
        self,
        similarity_score: float,
    ) -> float:
        return similarity_score * 100
    
    # Skill Match
    def skill_score(
        self,
        matched_skills: list,
        required_skills: list,
    ) -> float:
        if not required_skills:
            return 100
        return (
            len(matched_skills)
            / len(required_skills)
        ) * 100

    # Experience Score
    def experience_score(
        self,
        candidate_years: float,
        required_years: float,
    ) -> float:
        if required_years <= 0:
            return 100
        score = (
            candidate_years
            / required_years
        ) * 100
        return min(
            score,
            100,
        )

    # Education Score
    def education_score(
        self,
        matched: bool,
    ) -> float:
        return 100 if matched else 0
    
    # Certification Score
    def certification_score(
        self,
        matched: bool,
    ) -> float:
        return 100 if matched else 0

    # Final Score
    def final_score(
        self,
        similarity_score: float,
        rerank_score: float,
        matched_skills: list,
        required_skills: list,
        candidate_years: float,
        required_years: float,
        education_match: bool,
        certification_match: bool,
    ) -> float:
        semantic = self.semantic_score(
            similarity_score
        )
        rerank = rerank_score * 100
        skills = self.skill_score(
            matched_skills,
            required_skills,
        )
        experience = self.experience_score(
            candidate_years,
            required_years,
        )
        education = self.education_score(
            education_match,
        )
        certification = self.certification_score(
            certification_match,
        )
        score = (
            semantic * self.semantic_weight
            +
            rerank * self.rerank_weight
            +
            skills * self.skill_weight
            +
            experience * self.experience_weight
            +
            education * self.education_weight
            +
            certification * self.certification_weight
        )
        return round(score, 2)
    
    def extract_years(
        self,
        experience: str,
    ) -> float:
        if not experience:
            return 0
        experience = experience.strip()
        numbers = re.findall(r"\d+", experience)
        if not numbers:
            return 0
        if len(numbers) == 1:
            return float(numbers[0])
        return float(numbers[0])