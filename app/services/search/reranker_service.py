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
                settings.RERANKER_MODEL,
                max_length=256,
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

    def _build_candidate_text(
        self,
        candidate: dict,
    ) -> str:

        sections = []

        if candidate.get("designation"):
            sections.append(
                f"Designation: {candidate['designation']}"
            )

        if candidate.get("experience_years") is not None:
            sections.append(
                f"Experience: {candidate['experience_years']} years"
            )

        if candidate.get("summary"):
            sections.append(
                f"Summary: {candidate['summary']}"
            )

        skills = candidate.get("skills", [])
        if skills:
            sections.append(
                "Skills: " + ", ".join(skills)
            )

        education = candidate.get("education", [])
        if education:
            if isinstance(education, list):
                sections.append(
                    "Education: " + ", ".join(
                        [str(e) for e in education]
                    )
                )
            else:
                sections.append(
                    f"Education: {education}"
                )

        projects = candidate.get("projects", [])
        if projects:
            if isinstance(projects, list):
                project_names = []

                for project in projects:

                    if isinstance(project, dict):
                        project_names.append(
                            project.get(
                                "title",
                                project.get(
                                    "name",
                                    "",
                                ),
                            )
                        )
                    else:
                        project_names.append(str(project))

                sections.append(
                    "Projects: " + ", ".join(project_names)
                )

        certifications = candidate.get(
            "certifications",
            [],
        )

        if certifications:
            sections.append(
                "Certifications: "
                + ", ".join(
                    [str(c) for c in certifications]
                )
            )

        return "\n".join(sections)[: settings.RERANK_MAX_CHARS]

    # Batch Rerank
    def rerank_candidates(
        self,
        job_text: str,
        candidates: list,
    ) -> list:
        pairs = [
            (
                job_text,
                self._build_candidate_text(candidate),
            ) 
            for candidate in candidates
        ]
        scores = self.model.predict(
            pairs,
            batch_size=16,
            show_progress_bar=False,
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