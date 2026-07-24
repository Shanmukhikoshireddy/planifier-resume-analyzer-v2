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

from app.services.orchestrator.candidate_filter_service import (
    CandidateFilterService,
)

from app.prompts.reasoning_prompt import build_reasoning_prompt

import json


class SearchService:

    def __init__(self):

        self.job_repository = JobRepository()

        self.search_repository = SearchRepository()

        self.embedding_repository = EmbeddingRepository()

        self.profile_repository = ProfileRepository()

        self.embedding_service = EmbeddingService()

        self.cache_service = CacheService()

        self.reranker_service = RerankerService()

        self.scoring_service = ScoringService()

        self.candidate_filter_service = CandidateFilterService()

        self.openai_service = OpenAIService()
######
    # Public Entry######

    def execute(
        self,
        search_context: dict,
        page: int,
        page_size: int,
        conversation_message_id: str,
    ):

        return self.search(
            search_context=search_context,
            page=page,
            page_size=page_size,
            conversation_message_id=conversation_message_id,
        )
######
    # Search Pipeline######

    def search(
        self,
        search_context: dict,
        page: int,
        page_size: int,
        conversation_message_id: str,
    ):

        logger.info("=" * 80)
        logger.info("SEARCH PIPELINE STARTED")
        logger.info("=" * 80)

        job_id = search_context["job_id"]

        job = search_context["job"]

        job_position = search_context["job_position"]

        received_within = search_context["received_within"]

        original_prompt = search_context["original_prompt"]

        logger.info(f"Job Id : {job_id}")

        logger.info(f"Job Position : {job_position}")


        # Build Embedding Text


        job_text = self.build_job_embedding_text(job)


        # Generate Embedding


        embedding = self.embedding_service.generate_embedding(
            job_text
        )

        logger.info("Embedding Generated.")


        # Cache Lookup


        is_new_search = search_context.get(
            "is_new_search",
            True,
        )
        logger.info(f"is_new_search = {is_new_search}")
        logger.info(f"Search Context = {search_context}")

        if is_new_search:

            cached_job = self.cache_service.get_cached_job(
                embedding=embedding,
                job_position=job_position,
            )

        else:

            cached_job = None

        if cached_job:

            logger.info("CACHE HIT")

            results = self.search_repository.get_search_results(
                job_id=job_id,
                conversation_message_id=conversation_message_id,
            )

            # Update Current Conversation Job

            self.job_repository.update_job(
                job_id=job_id,
                update_fields={
                    "prompt": job,
                    "job_embedding": embedding,
                    "original_prompt": original_prompt,
                },
            )

            start = (page - 1) * page_size

            end = start + page_size

            return {

                "job_id": job_id,

                "cached": True,

                "page": page,

                "page_size": page_size,

                "total_candidates": len(results),

                "total_pages": (
                    len(results)
                    + page_size
                    - 1
                ) // page_size,

                "results": results[start:end],

            }

        else:
            logger.info("CACHE MISS")


        # Update Current Job


        self.job_repository.update_job(
            job_id=job_id,
            update_fields={
                "prompt": job,
                "job_embedding": embedding,
                "original_prompt": original_prompt,
            },
        )


        # Continue Search


        return self.vector_search(

            job_id=job_id,

            job=job,

            job_text=job_text,

            job_embedding=embedding,

            job_position=job_position,

            received_within=received_within,

            page=page,

            page_size=page_size,

            conversation_message_id=conversation_message_id,

        )
    
######
    # List -> Text######

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

            elif item is not None:

                output.append(str(item))

        return "\n".join(output)
######
    # Build Embedding Text######

    def build_job_embedding_text(
        self,
        job: dict,
    ) -> str:


        # Experience


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

        elif experience:

            experience_text = str(experience)


        # Required Skills


        required_skills = []

        for skill in job.get(
            "required_skills",
            [],
        ):

            if not isinstance(skill, dict):
                continue

            required_skills.extend(
                skill.get(
                    "search_terms",
                    [],
                )
            )


        # Preferred Skills


        preferred_skills = []

        for skill in job.get(
            "preferred_skills",
            [],
        ):

            if not isinstance(skill, dict):
                continue

            preferred_skills.extend(
                skill.get(
                    "search_terms",
                    [],
                )
            )


        # Excluded Skills


        excluded_skills = []

        for skill in job.get(
            "excluded_skills",
            [],
        ):

            if not isinstance(skill, dict):
                continue

            excluded_skills.extend(
                skill.get(
                    "search_terms",
                    [],
                )
            )


        # Sections


        sections = [

            job.get(
                "title",
                "",
            ),

            experience_text,

            job.get(
                "education",
                "",
            ),

            job.get(
                "location",
                "",
            ),

            " ".join(required_skills),

            " ".join(preferred_skills),

            " ".join(excluded_skills),

            self.list_to_text(
                job.get(
                    "certifications",
                    [],
                )
            ),

            self.list_to_text(
                job.get(
                    "responsibilities",
                    [],
                )
            ),

            self.list_to_text(
                job.get(
                    "qualifications",
                    [],
                )
            ),

            self.list_to_text(
                job.get(
                    "nice_to_have",
                    [],
                )
            ),

            self.list_to_text(
                job.get(
                    "keywords",
                    [],
                )
            ),

        ]


        # Final Embedding Text


        return "\n".join(

            str(section)

            for section in sections

            if section

        )
    


######
    # Vector Search######

    def vector_search(
        self,
        job_id,
        job,
        job_text,
        job_embedding,
        job_position,
        received_within,
        page,
        page_size,
        conversation_message_id,
    ):

        logger.info("=" * 80)
        logger.info("ATLAS VECTOR SEARCH")
        logger.info("=" * 80)


        # Atlas Search


        vector_results = (
            self.embedding_repository.search_similar_embeddings(
                embedding=job_embedding,
                job_position=job_position,
                received_within=received_within,
            )
        )

        logger.info(
            f"Vector Search returned {len(vector_results)} candidates."
        )


        # Load Candidate Profiles


        candidates = []

        for result in vector_results:
            logger.info(result)

            profile = self.profile_repository.get_profile(
                result["profile_id"]
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


        # No Candidates


        if not candidates:

            logger.warning(
                "No candidates found from vector search."
            )

            self.job_repository.update_result_count(
                job_id,
                0,
            )

            self.job_repository.update_status(
                job_id,
                "COMPLETED",
            )

            return self.rerank_candidates(
                job_id=job_id,
                job=job,
                job_text=job_text,
                candidates=candidates,
                page=page,
                page_size=page_size,
                conversation_message_id=conversation_message_id,
            )


        # Business Rule Filtering


        logger.info("=" * 80)
        logger.info("BUSINESS RULE FILTERING")
        logger.info("=" * 80)

        logger.info(
            f"Before Filtering : {len(candidates)}"
        )

        candidates = self.candidate_filter_service.filter(

            candidates,

            job,

        )

        logger.info(
            f"After Filtering : {len(candidates)}"
        )


        # Nothing Left


        if not candidates:

            logger.warning(
                "No candidates remained after filtering."
            )

            self.job_repository.update_result_count(
                job_id,
                0,
            )

            self.job_repository.update_status(
                job_id,
                "COMPLETED",
            )

            return {

                "job_id": job_id,

                "cached": False,

                "page": page,

                "page_size": page_size,

                "total_candidates": 0,

                "total_pages": 0,

                "results": [],

            }


        # Continue Pipeline


        return self.rerank_candidates(
                job_id=job_id,
                job=job,
                job_text=job_text,
                candidates=candidates,
                page=page,
                page_size=page_size,
                conversation_message_id=conversation_message_id,
            )
    
######
    # Rerank Candidates######

    def rerank_candidates(
        self,
        job_id,
        job,
        job_text,
        candidates,
        page,
        page_size,
        conversation_message_id,
    ):

        logger.info("=" * 80)
        logger.info("CROSS ENCODER RERANKING")
        logger.info("=" * 80)


        # Build Resume Text


        for candidate in candidates:

            skills = candidate.get(
                "skills",
                [],
            )

            education = candidate.get(
                "education",
                [],
            )

            projects = candidate.get(
                "projects",
                [],
            )

            certifications = candidate.get(
                "certifications",
                [],
            )

            # Future Optimization
            # If resume_text is already generated during
            # ingestion, reuse it.

            resume_text = candidate.get(
                "resume_text"
            )

            if not resume_text:

                resume_text = f"""
Candidate
{candidate.get("candidate_name","")}

Designation
{candidate.get("designation","")}

Job Position
{candidate.get("job_position","")}

Experience
{candidate.get("experience_years",0)}

Professional Summary
{candidate.get("summary","")}

Skills
{self.list_to_text(skills)}

Education
{self.list_to_text(education)}

Projects
{self.list_to_text(projects)}

Certifications
{self.list_to_text(certifications)}

Current Company
{candidate.get("current_company","")}
""".strip()

                candidate["resume_text"] = resume_text


        # Cross Encoder


        logger.info(
            f"Running reranker for {len(candidates)} candidates."
        )

        candidates = self.reranker_service.rerank_candidates(

            job_text,

            candidates,

        )

        logger.info(
            "Cross Encoder Reranking Completed."
        )


        # Continue Pipeline


        return self.score_candidates(

            job_id=job_id,

            job=job,

            candidates=candidates,

            page=page,

            page_size=page_size,

            conversation_message_id=conversation_message_id,

        )
    

######
    # ATS Scoring######

    def score_candidates(
        self,
        job_id,
        job,
        candidates,
        page,
        page_size,
        conversation_message_id,
    ):

        logger.info("=" * 80)
        logger.info("ATS SCORING")
        logger.info("=" * 80)

        scored_candidates = []

        total_required_skills = len(
            job.get(
                "required_skills",
                [],
            )
        )


        # Score Each Candidate


        for candidate in candidates:

            # ATS Calculation

            score = self.scoring_service.calculate_score(

                job=job,

                candidate=candidate,

            )

            # Update Candidate

            candidate.update({

                "matched_skills":
                    score["matched_skills"],

                "missing_skills":
                    score["missing_skills"],

                "matched_preferred_skills":
                    score["matched_preferred_skills"],

                "matched_certifications":
                    score["matched_certifications"],

                "education_match":
                    score["education_match"],

                "score_breakdown":
                    score["score_breakdown"],

                "final_score":
                    score["final_score"],

            })

            # Skill Match %

            if total_required_skills:

                skill_percentage = (

                    len(score["matched_skills"])

                    /

                    total_required_skills

                ) * 100

            else:

                skill_percentage = 100

            candidate["skill_match_percentage"] = round(

                skill_percentage,

                2,

            )

            # Match Level

            final_score = candidate["final_score"]

            if final_score >= 90:

                level = "Excellent"

            elif final_score >= 80:

                level = "Very Good"

            elif final_score >= 70:

                level = "Good"

            elif final_score >= 55:

                level = "Average"

            elif final_score >= 40:

                level = "Weak"

            else:

                level = "Poor"

            candidate["match_level"] = level

            scored_candidates.append(candidate)


        # Final Ranking


        scored_candidates.sort(

            key=lambda candidate: (

                candidate.get(
                    "final_score",
                    0,
                ),

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


        # Pagination


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


        # Continue Pipeline


        return self.generate_reasoning(

            job_id=job_id,

            candidates=scored_candidates,

            total_candidates=total_candidates,

            total_pages=total_pages,

            page=page,

            page_size=page_size,

            conversation_message_id=conversation_message_id,

        )
    
######
    # Generate Reasoning######

    def generate_reasoning(
        self,
        job_id,
        candidates,
        total_candidates,
        total_pages,
        page,
        page_size,
        conversation_message_id,
    ):

        logger.info("=" * 80)
        logger.info("FINALIZING SEARCH")
        logger.info("=" * 80)


        # Lazy Reasoning


        for candidate in candidates:

            candidate["reasoning"] = None

            candidate["reasoning_generated"] = False


        # Save Search Results


        self.search_repository.save_search_results(
            job_id=job_id,
            candidates=candidates,
            conversation_message_id=conversation_message_id,
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


        # Pagination


        start = (

            page - 1

        ) * page_size

        end = start + page_size

        logger.info(

            f"Search completed successfully with {total_candidates} candidates."

        )

        return {

            "job_id": job_id,

            "cached": False,

            "page": page,

            "page_size": page_size,

            "total_candidates": total_candidates,

            "total_pages": total_pages,

            "results": candidates[start:end],

        }
    
######
    # Candidate Reasoning######

    def get_candidate_reasoning(
        self,
        job_id: str,
        profile_id: str,
    ):

        logger.info("=" * 80)
        logger.info("CANDIDATE REASONING")
        logger.info("=" * 80)


        # Cache


        cached = self.search_repository.get_reasoning(

            job_id,

            profile_id,

        )

        if (

            cached

            and

            cached.get(

                "reasoning_generated",

                False,

            )

        ):

            logger.info("Reasoning Cache Hit.")

            return {

                "profile_id": profile_id,

                "reasoning": cached["reasoning"],

                "cached": True,

            }


        # Candidate


        candidate = self.search_repository.get_candidate(

            job_id,

            profile_id,

        )

        if candidate is None:

            return {

                "message": "Candidate not found."

            }


        # Job


        job = self.job_repository.get_job(

            job_id,

        )

        if job is None:

            return {

                "message": "Job not found."

            }


        # Candidate Context


        candidate_context = {

            "candidate_name":

                candidate.get("candidate_name"),

            "designation":

                candidate.get("designation"),

            "job_position":

                candidate.get("job_position"),

            "experience_years":

                candidate.get("experience_years"),

            "summary":

                candidate.get("summary"),

            "skills":

                candidate.get("skills", []),

            "education":

                candidate.get("education", []),

            "projects":

                candidate.get("projects", []),

            "certifications":

                candidate.get("certifications", []),

            "matched_skills":

                candidate.get("matched_skills", []),

            "missing_skills":

                candidate.get("missing_skills", []),

            "matched_preferred_skills":

                candidate.get(

                    "matched_preferred_skills",

                    [],

                ),

            "matched_certifications":

                candidate.get(

                    "matched_certifications",

                    [],

                ),

            "education_match":

                candidate.get(

                    "education_match",

                ),

            "skill_match_percentage":

                candidate.get(

                    "skill_match_percentage",

                    0,

                ),

            "final_score":

                candidate.get(

                    "final_score",

                    0,

                ),

            "match_level":

                candidate.get(

                    "match_level",

                    "",

                ),

        }


        # Job Context


        job_context = {

            "title":

                job.get("title"),

            "experience":

                job.get("experience"),

            "education":

                job.get("education"),

            "location":

                job.get("location"),

            "required_skills":

                job.get(

                    "required_skills",

                    [],

                ),

            "preferred_skills":

                job.get(

                    "preferred_skills",

                    [],

                ),

            "excluded_skills":

                job.get(

                    "excluded_skills",

                    [],

                ),

            "responsibilities":

                job.get(

                    "responsibilities",

                    [],

                ),

            "qualifications":

                job.get(

                    "qualifications",

                    [],

                ),

            "nice_to_have":

                job.get(

                    "nice_to_have",

                    [],

                ),

            "certifications":

                job.get(

                    "certifications",

                    [],

                ),

        }


        # Prompt


        prompt = build_reasoning_prompt(

            job_context,

            candidate_context,

        )


        # LLM


        reasoning = self.openai_service.generate(

            prompt

        )


        # Save


        self.search_repository.save_reasoning(

            job_id,

            profile_id,

            reasoning,

        )

        logger.info("Reasoning Generated.")

        return {

            "profile_id": profile_id,

            "reasoning": reasoning,

            "cached": False,

        }