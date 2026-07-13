from sentence_transformers import CrossEncoder
from app.config.settings import settings
from app.config.logging import logger

class RerankerService:
    """
    Cross Encoder Reranker
    Input:
        Job Description
        Candidate Resume Text
    Output:
        Relevance Score
    """
    _model = None
    def __init__(self):
        if RerankerService._model is None:
            logger.info(
                f"Loading Reranker : {settings.RERANKER_MODEL}"
            )
            RerankerService._model = CrossEncoder(
                settings.RERANKER_MODEL
            )
            logger.info( "Reranker Loaded.")
        self.model = RerankerService._model

    # Score Single Candidate
    def rerank(
        self,
        job_text: str,
        resume_text: str,
    ) -> float:
        score = self.model.predict(
            [
                (
                    job_text,
                    resume_text,
                )
            ]
        )[0]
        return float(score)

    # Batch Rerank
    def rerank_candidates(
        self,
        job_text: str,
        candidates: list,
    ) -> list:
        pairs = [
            (
                job_text,
                candidate["resume_text"],
            )
            for candidate in candidates
        ]
        scores = self.model.predict(
            pairs
        )
        for candidate, score in zip(
            candidates,
            scores,
        ):
            candidate["rerank_score"] = float(
                score
            )
        candidates.sort(
            key=lambda x: x["rerank_score"],
            reverse=True,
        )
        return candidates

    # Top K Candidates
    def top_candidates(
        self,
        candidates: list,
        top_k: int = 20,
    ):
        return candidates[:top_k]