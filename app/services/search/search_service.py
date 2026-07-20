from app.config.logging import logger
from app.repository.job_repository import JobRepository
from app.repository.search_repository import SearchRepository
from app.repository.embedding_repository import EmbeddingRepository
from app.repository.profile_repository import ProfileRepository
from app.services.shared.openai_service import OpenAIService
from app.services.ingestion.embedding_service import EmbeddingService
from app.services.search.cache_service import CacheService
from app.services.search.reranker_service import RerankerService
from app.services.search.scoring_service import ScoringService
from app.services.orchestrator.prompt_parser_service import PromptParserService
# from app.prompts.job_prompt import build_job_prompt
from app.prompts.reasoning_prompt import build_reasoning_prompt
from app.services.orchestrator.candidate_filter_service import CandidateFilterService
import re
import json
class SearchService:
    def __init__(self):
        self.job_repository = JobRepository()
        self.search_repository = SearchRepository()
        self.embedding_repository = EmbeddingRepository()
        self.profile_repository = ProfileRepository()

        self.prompt_parser_service = PromptParserService()
        self.openai_service = OpenAIService()
        self.embedding_service = EmbeddingService()
        self.cache_service = CacheService()
        self.reranker_service = RerankerService()
        self.scoring_service = ScoringService()
        self.candidate_filter_service = CandidateFilterService()

    # Search
    def search(
        self,
        job_position: str,
        job_description: str,
        received_within: str,
        page: int,
        page_size: int,
    ):
        logger.info("=" * 80)
        logger.info("STARTING CANDIDATE SEARCH")
        logger.info("=" * 80)

        logger.info("USER PROMPT")
        logger.info(job_description)

        # Parse the user prompt into a structured job
        job = self.prompt_parser_service.parse(job_description)

        logger.info("PARSED JOB")
        logger.info(job)

        if not job.get("title"):
            logger.warning(
                "No title extracted from prompt."
            )

        if not job.get("required_skills"):
            logger.warning(
                "No skills extracted from prompt."
            )

        logger.info("Prompt parsed successfully.")

        # Continue existing search pipeline
        return self.process_job(
            job=job,
            job_position=job_position,
            original_job_description=job_description,
            received_within=received_within,
            page=page,
            page_size=page_size,
        )

    def list_to_text(
        self,
        items,
    ) -> str:

        if not items:
            return ""

        output = []

        for item in items:

            if isinstance(item, str):

                output.append(item)

            elif isinstance(item, dict):

                output.append(
                    json.dumps(
                        item,
                        ensure_ascii=False,
                    )
                )

            else:

                output.append(str(item))

        return "\n".join(output)
    # Build Job Embedding Text
    def build_job_embedding_text(
        self,
        job: dict,
    ) -> str:

        experience = job.get("experience") or {}

        experience_text = ""

        if isinstance(experience, dict):

            minimum = experience.get("min")
            maximum = experience.get("max")

            if minimum is not None and maximum is not None:
                experience_text = f"{minimum}-{maximum} years"

            elif minimum is not None:
                experience_text = f"{minimum}+ years"

            elif maximum is not None:
                experience_text = f"Up to {maximum} years"

        else:
            experience_text = str(experience)

        sections = [
            job.get("title", ""),
            experience_text,
            job.get("education", ""),
            job.get("location", ""),
            " ".join(
                " ".join(skill.get("search_terms", []))
                for skill in job.get("required_skills", [])
                if isinstance(skill, dict)
            ),
            " ".join(
                " ".join(skill.get("search_terms", []))
                for skill in job.get("preferred_skills", [])
                if isinstance(skill, dict)
            ),

            self.list_to_text(job.get("certifications", [])),

            self.list_to_text(job.get("responsibilities", [])),

            self.list_to_text(job.get("qualifications", [])),

            self.list_to_text(job.get("nice_to_have", [])),
            " ".join(job.get("keywords", [])),
        ]

        return "\n".join(
            str(section)
            for section in sections
            if section
        )

    # Process Job
    def process_job(
        self,
        job: dict,
        job_position: str,
        original_job_description: str,
        received_within: str,
        page: int,
        page_size: int,
    ):
        # Build Embedding Text
        job_text = self.build_job_embedding_text(
            job
        )

        # Generate Embedding
        job_embedding = self.embedding_service.generate_embedding(
            job_text
        )
        logger.info("Job embedding generated.")

        # Cache Lookup
        cached_job = self.cache_service.find_similar_job(
            embedding=job_embedding,
            job_position=job_position,
        )

        if cached_job:
            logger.info("Cache Hit.")
            results = self.search_repository.get_search_results(
                str(cached_job["_id"])
            )
            start = (page - 1) * page_size
            end = start + page_size
            return {
                "job_id": str(cached_job["_id"]),
                "page": page,
                "page_size": page_size,
                "total_candidates": len(results),
                "total_pages": (len(results)+ page_size- 1) // page_size,
                "results": results[start:end],
            }
        logger.info("Cache Miss.")

        # Save Job
        job_id = self.job_repository.create_job(
            job=job,
            original_job_description=original_job_description,
            embedding=job_embedding,
            job_position=job_position,
            received_within=received_within,)

        logger.info(f"Job Created : {job_id}")
        return self.vector_search(
            job_id=job_id,
            job=job,
            job_text=job_text,
            job_embedding=job_embedding,
            job_position=job_position,
            received_within=received_within,
            page=page,
            page_size=page_size,
        )
    
    # Vector Search
    def vector_search(
        self,
        job_id: str,
        job: dict,
        job_text: str,
        job_embedding: list,
        job_position: str,
        received_within: str,
        page: int,
        page_size: int,
    ):
        logger.info("Running Atlas Vector Search...")

        vector_results = self.embedding_repository.search_similar_embeddings(
            embedding=job_embedding,
            job_position=job_position,
            received_within=received_within,
        )

        logger.info(f"Retrieved {len(vector_results)} candidates.")

        candidates = []

        for result in vector_results:

            profile = self.profile_repository.get_profile(
                result["resume_id"]
            )

            if profile is None:
                continue

            profile["semantic_score"] = result.get(
                "embedding_score",
                0,
            )

            candidates.append(profile)

        logger.info(
            f"Loaded {len(candidates)} candidate profiles."
        )

        if not candidates:

            logger.warning("No candidates found.")

            return {
                "job_id": job_id,
                "page": page,
                "page_size": page_size,
                "total_candidates": 0,
                "total_pages": 0,
                "results": [],
            }

        ####################################################
        # Business Rule Filtering
        ####################################################

        logger.info("=" * 80)
        logger.info("BUSINESS RULE FILTERING")
        logger.info("=" * 80)

        logger.info(
            f"Candidates before filtering : {len(candidates)}"
        )

        candidates = self.candidate_filter_service.filter(
            candidates,
            job,
        )

        logger.info(
            f"Candidates after filtering : {len(candidates)}"
        )

        if not candidates:

            logger.warning(
                "No candidates remained after filtering."
            )

            return {
                "job_id": job_id,
                "page": page,
                "page_size": page_size,
                "total_candidates": 0,
                "total_pages": 0,
                "results": [],
            }

        ####################################################
        # Cross Encoder + ATS
        ####################################################

        return self.rerank_candidates(
            job_id=job_id,
            job=job,
            job_text=job_text,
            candidates=candidates,
            page=page,
            page_size=page_size,
        )

    # Rerank Candidates
    def rerank_candidates(
        self,
        job_id: str,
        job: dict,
        job_text: str,
        candidates: list,
        page: int,
        page_size: int,
    ):
        logger.info("Running Cross Encoder Reranker...")

        # Build Resume Text
        for candidate in candidates:
            skills = candidate.get("skills",[],)
            education = candidate.get("education",[],)
            projects = candidate.get("projects",[],)
            certifications = candidate.get("certifications",[],)
            candidate["resume_text"] = f"""
                Candidate
                {candidate.get("candidate_name", "")}
                Designation
                {candidate.get("designation", "")}
                job_position
                {candidate.get("job_position", "")}
                Experience
                {candidate.get("experience_years", 0)}
                Summary
                {candidate.get("summary", "")}
                Skills
                {self.list_to_text(skills)}
                Education
                {self.list_to_text(education)}
                Projects
                {self.list_to_text(projects)}
                Certifications
                {self.list_to_text(certifications)}
                Current Company
                {candidate.get("current_company", "")}
                """.strip()

        # Cross Encoder
        candidates = self.reranker_service.rerank_candidates(
            job_text,
            candidates,
        )
        logger.info(f"Reranked {len(candidates)} candidates.")
        return self.score_candidates(
            job_id=job_id,
            job=job,
            candidates=candidates,
            page=page,
            page_size=page_size,
        )
    
    def score_candidates(
        self,
        job_id: str,
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

            #############################################
            # Calculate ATS
            #############################################

            result = self.scoring_service.calculate_score(

                job=job,

                candidate=candidate,

            )

            #############################################
            # Update Candidate
            #############################################

            candidate.update({

                "matched_skills":
                    result["matched_skills"],

                "missing_skills":
                    result["missing_skills"],

                "matched_preferred_skills":
                    result["matched_preferred_skills"],

                "matched_certifications":
                    result["matched_certifications"],

                "education_match":
                    result["education_match"],

                "score_breakdown":
                    result["score_breakdown"],

                "final_score":
                    result["final_score"],

            })

            #####################################################
            # Skill Match %
            #####################################################

            total_required = len(
                job.get(
                    "required_skills",
                    [],
                )
            )

            if total_required:

                candidate["skill_match_percentage"] = round(

                    (
                        len(
                            result["matched_skills"]
                        )
                        /
                        total_required
                    ) * 100,

                    2,

                )

            else:

                candidate["skill_match_percentage"] = 100

            #####################################################
            # Overall Match Level
            #####################################################

            score = result["final_score"]

            if score >= 90:
                level = "Excellent"

            elif score >= 80:
                level = "Very Good"

            elif score >= 70:
                level = "Good"

            elif score >= 55:
                level = "Average"

            elif score >= 40:
                level = "Weak"

            else:
                level = "Poor"

            candidate["match_level"] = level

            scored_candidates.append(candidate)

        #########################################################
        # Sorting
        #########################################################

        scored_candidates.sort(

            key=lambda candidate: (

                candidate["final_score"],

                candidate.get(
                    "rerank_score",
                    0,
                ),

                candidate.get(
                    "semantic_score",
                    0,
                ),

            ),

            reverse=True,

        )

        #########################################################

        total_candidates = len(scored_candidates)

        total_pages = (

            total_candidates
            +
            page_size
            -
            1

        ) // page_size

        logger.info(

            f"ATS completed for {total_candidates} candidates."

        )

        return self.generate_reasoning(

            job_id=job_id,

            candidates=scored_candidates,

            total_candidates=total_candidates,

            total_pages=total_pages,

            page=page,

            page_size=page_size,

        )
    # Generate Reasoning
    def generate_reasoning(
        self,
        job_id: str,
        candidates: list,
        total_candidates: int,
        total_pages: int,
        page: int,
        page_size: int,
    ):
        logger.info(
            "Generating Candidate Reasoning..."
        )
        # Currently reasoning is generated lazily
        # when the frontend requests a single candidate.---
        for candidate in candidates:
            candidate["reasoning"] = None
            candidate["reasoning_generated"] = False
        # Save Results
        self.search_repository.save_search_results(
            job_id,
            candidates,
        )
        # Update Job
        self.job_repository.update_result_count(
            job_id,
            total_candidates,
        )
        self.job_repository.update_status(
            job_id,
            "COMPLETED",
        )
        logger.info(
            "Search Completed."
        )
        start = (
            page - 1
        ) * page_size
        end = start + page_size
        return {
            "job_id": job_id,
            "page": page,
            "page_size": page_size,
            "total_candidates": total_candidates,
            "total_pages": total_pages,
            "results": candidates[start:end],
        }

    # Candidate Reasoning
    def get_candidate_reasoning(
        self,
        job_id: str,
        resume_id: str,
    ):
        logger.info(f"Generating reasoning for {resume_id}")

        # Cached Reasoning
        reasoning = self.search_repository.get_reasoning(job_id,resume_id,)
        if (reasoning and reasoning.get("reasoning_generated",False,)):
            logger.info("Reasoning Cache Hit.")
            return {
                "resume_id": resume_id,
                "reasoning": reasoning.get("reasoning","",),
                "cached": True,
            }

        # Candidate
        candidate = self.search_repository.get_candidate(
            job_id,
            resume_id,
        )
        if candidate is None:
            return {
                "message": "Candidate not found."
            }

        job = self.job_repository.get_job(job_id,)
        if job is None:
            return {
                "message": "Job not found."
            }

        # Build Clean Candidate Context
        candidate_context = {
            "candidate_name": candidate.get("candidate_name"),
            "designation": candidate.get("designation"),
            "job_position": candidate.get("job_position"),
            "experience_years": candidate.get("experience_years"),
            "summary": candidate.get("summary"),
            "skills": candidate.get("skills",[],),
            "education": candidate.get("education",[],),
            "projects": candidate.get("projects",[],),
            "certifications": candidate.get("certifications",[],),
            "matched_skills": candidate.get("matched_skills",[],),
            "missing_skills": candidate.get("missing_skills",[],),
            "skill_match_percentage": candidate.get("skill_match_percentage",0,),
            "final_score": candidate.get("final_score",0,),
        }

        # Build Clean Job Context
        job_context = {
            "title": job.get("title"),
            "experience": job.get("experience"),
            "education": job.get("education"),
            "required_skills": job.get(
                "required_skills",
                [],
            ),

            "preferred_skills": job.get(
                "preferred_skills",
                [],
            ),

            "excluded_skills": job.get(
                "excluded_skills",
                [],
            ),
            "responsibilities": job.get("responsibilities",[],),
            "qualifications": job.get("qualifications",[],),
            "nice_to_have": job.get("nice_to_have",[],),
        }

        logger.info("JOB CONTEXT")
        logger.info(job_context)
        logger.info("CANDIDATE CONTEXT")
        logger.info(candidate_context)
        prompt = build_reasoning_prompt(
            job_context,
            candidate_context,
        )
        reasoning_text = self.openai_service.generate(
            prompt
        )

        # Save
        self.search_repository.save_reasoning(
            job_id,
            resume_id,
            reasoning_text,
        )

        logger.info("Reasoning Generated.")
        return {
            "resume_id": resume_id,
            "reasoning": reasoning_text,
            "cached": False,
        }