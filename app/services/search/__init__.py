from app.config.settings import settings
import re

class ScoringService:
    """
    Calculates the final ATS score for a candidate.
    """
    def __init__(self):
        # Weight of MongoDB Atlas Vector Search score
        self.semantic_weight = settings.SEMANTIC_WEIGHT

        # Weight of CrossEncoder reranker score
        self.rerank_weight = settings.RERANK_WEIGHT

        # Weight of skill matching
        self.skill_weight = settings.SKILL_WEIGHT

        # Weight of experience matching
        self.experience_weight = settings.EXPERIENCE_WEIGHT

        # Weight of education matching
        self.education_weight = settings.EDUCATION_WEIGHT

        # Weight of certification matching
        self.certification_weight = settings.CERTIFICATION_WEIGHT