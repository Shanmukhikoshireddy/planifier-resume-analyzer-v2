from app.config.logging import logger
from app.config.settings import settings

from app.repository.search_repository import SearchRepository
from app.repository.profile_repository import ProfileRepository

from app.services.shared.openai_service import OpenAIService
from app.services.ingestion.embedding_service import EmbeddingService

from app.services.search.reranker_service import RerankerService
from app.services.search.scoring_service import ScoringService

from app.services.orchestrator.candidate_filter_service import (
    CandidateFilterService,
)

from app.prompts.reasoning_prompt import build_reasoning_prompt

import json


class SearchService:

    def __init__(self):

        self.search_repository = SearchRepository()

        self.profile_repository = ProfileRepository()

        self.embedding_service = EmbeddingService()

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

        search_id = search_context.get("search_id") or ""

        # Create a Mongo search document for a brand-new search
        # before any repository update is attempted.
        if not search_id:
            logger.info(
                "No search_id provided. Creating new search."
            )

            search_id = (
                self.search_repository.create_empty_search()
            )

            logger.info(
                f"Created new search_id: {search_id}"
            )

            search_context["search_id"] = search_id

        parsed_search = search_context.get("parsed_search", {})

        job_position_id = search_context.get("job_position_id")

        received_within = search_context.get("received_within")

        global_search_allowed = search_context.get("global_search_allowed", True)

        original_prompt = search_context.get("original_prompt", "")

        # is_new_search is intentionally honored by execute() as a fresh
        # vector-search request. Previous candidates are only reused by
        # refine_previous_results(), which is called for SEARCH_MODIFICATION.
        is_new_search = search_context.get("is_new_search", True)
        logger.info(f"Independent search execution: {is_new_search}")

        logger.info(f"Job Id : {job_position_id}")

        logger.info(f"Job Position : {job_position_id}")


        # Build Embedding Text


        job_text = self.build_search_embedding_text(parsed_search)


        # Generate Embedding

        logger.info("=" * 80)
        logger.info("EMBEDDING TEXT")
        logger.info(job_text)
        logger.info("=" * 80)
        embedding = self.embedding_service.generate_embedding(
            job_text
        )

        logger.info("Embedding Generated.")



        # Update Current Job


        self.search_repository.update_search(
            search_id=search_id,
            update_fields={
                "title": parsed_search.get("title", ""),
                "job_position_id": job_position_id,
                "parsed_search": parsed_search,
                "search_embedding": embedding,
                "original_prompt": original_prompt,
                "received_within": received_within,
                "global_search_allowed": global_search_allowed,
            },
        )


        # Continue Search


        return self.vector_search(
            search_id=search_id,
            parsed_search=parsed_search,
            job_text=job_text,
            search_embedding=embedding,
            job_position_id=job_position_id,
            received_within=received_within,
            global_search_allowed=global_search_allowed,
            page=page,
            page_size=page_size,
            conversation_message_id=conversation_message_id,
        )
    
######
    # List -> Text######

    def _limit_for_rerank(self, candidates: list) -> list:
        candidates.sort(
            key=lambda item: item.get("semantic_score", 0),
            reverse=True,
        )

        rerank_limit = settings.RERANK_TOP_K

        if len(candidates) > rerank_limit:
            logger.info(
                "Limiting rerank to top %s of %s candidates.",
                rerank_limit,
                len(candidates),
            )
            return candidates[:rerank_limit]

        return candidates

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

    def build_search_embedding_text(
        self,
        parsed_search: dict,
    ) -> str:


        # Experience


        experience = parsed_search.get("experience") or {}

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

        for skill in parsed_search.get(
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

        for skill in parsed_search.get(
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

        for skill in parsed_search.get(
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

            parsed_search.get(
                "title",
                "",
            ),

            experience_text,

            parsed_search.get(
                "education",
                "",
            ),

            parsed_search.get(
                "location",
                "",
            ),

            " ".join(required_skills),

            " ".join(preferred_skills),

            " ".join(excluded_skills),

            self.list_to_text(
                parsed_search.get(
                    "certifications",
                    [],
                )
            ),

            self.list_to_text(
                parsed_search.get(
                    "responsibilities",
                    [],
                )
            ),

            self.list_to_text(
                parsed_search.get(
                    "qualifications",
                    [],
                )
            ),

            self.list_to_text(
                parsed_search.get(
                    "nice_to_have",
                    [],
                )
            ),

            self.list_to_text(
                parsed_search.get(
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
    

    ############################################################
    # Refine Previous Results
    ############################################################

    def refine_previous_results(
        self,
        search_context,
        page,
        page_size,
        conversation_message_id,
        previous_result_message_id,
    ):

        logger.info("=" * 80)
        logger.info("REFINING PREVIOUS SEARCH")
        logger.info("=" * 80)

        search_id = search_context.get(
            "search_id"
        ) or ""

        # Refinement requires an existing search. Never fall back
        # to a global search when the search_id is missing.
        if not search_id:
            logger.warning(
                "SEARCH_MODIFICATION received without search_id."
            )

            return {
                "search_id": search_id,
                "page": page,
                "page_size": page_size,
                "total_candidates": 0,
                "total_pages": 0,
                "results": [],
            }

        parsed_search = (
            search_context.get(
                "parsed_search",
                {},
            )
            or {}
        )

        previous_search = (
            search_context.get(
                "previous_search",
                {},
            )
            or {}
        )

        modification_search = (
            search_context.get(
                "modification_search",
                {},
            )
            or {}
        )

        logger.info(
            f"Previous search: {previous_search}"
        )

        logger.info(
            f"Modification search: {modification_search}"
        )

        logger.info(
            f"Merged search: {parsed_search}"
        )

        # ========================================================
        # BUILD EMBEDDING TEXT FROM MERGED SEARCH
        # ========================================================

        job_text = self.build_search_embedding_text(
            parsed_search
        )

        logger.info("=" * 80)
        logger.info("REFINEMENT EMBEDDING TEXT")
        logger.info(job_text)
        logger.info("=" * 80)

        # ========================================================
        # LOAD PREVIOUS CANDIDATES
        # ========================================================

        previous_candidates = (
            self.search_repository
            .get_results_by_conversation_message(
                previous_result_message_id
            )
        )

        if not previous_candidates and search_id:
            logger.info(
                f"previous_result_message_id {previous_result_message_id} had no results. "
                f"Trying get_latest_search_results fallback for search_id={search_id}."
            )
            previous_candidates = (
                self.search_repository
                .get_latest_search_results(
                    search_id
                )
            )

        logger.info(
            f"Loaded {len(previous_candidates)} previous candidates."
        )

        # ========================================================
        # IMPORTANT
        #
        # A SEARCH_MODIFICATION must NOT fall back to a global
        # vector search.
        #
        # Example:
        #
        # Previous:
        # Python developers
        #
        # Modification:
        # 3+ years
        #
        # We must filter previous Python candidates.
        #
        # We must NOT search globally for "3+ years".
        # ========================================================

        if not previous_candidates:

            logger.warning(
                "No previous candidates found for refinement."
            )

            logger.warning(
                "NOT falling back to global vector search."
            )

            self.search_repository.update_result_count(
                search_id,
                0,
            )

            self.search_repository.update_status(
                search_id,
                "COMPLETED",
            )

            return {
                "search_id": search_id,
                "page": page,
                "page_size": page_size,
                "total_candidates": 0,
                "total_pages": 0,
                "results": [],
            }

        # ========================================================
        # COPY CANDIDATES
        #
        # Do not modify Mongo result objects directly.
        # ========================================================

        cleaned_candidates = []

        for candidate in previous_candidates:

            candidate = dict(candidate)

            candidate.pop(
                "_id",
                None,
            )

            candidate.pop(
                "search_id",
                None,
            )

            candidate.pop(
                "conversation_message_id",
                None,
            )

            candidate.pop(
                "created_at",
                None,
            )

            candidate.pop(
                "status",
                None,
            )

            candidate.pop(
                "rank",
                None,
            )

            cleaned_candidates.append(
                candidate
            )

        logger.info(
            f"Candidates before refinement filters: {len(cleaned_candidates)}"
        )

        # ========================================================
        # APPLY MERGED BUSINESS FILTERS
        #
        # IMPORTANT:
        # parsed_search must be the MERGED search.
        #
        # Example:
        #
        # Python + 3 years + Telangana
        # ========================================================

        candidates = (
            self.candidate_filter_service.filter(
                cleaned_candidates,
                parsed_search,
            )
        )
        logger.info(
            "FINAL EXPERIENCE BEFORE FILTER: %s",
            parsed_search.get("experience"),
        )

        logger.info(
            f"After refinement filters: {len(candidates)}"
        )

        candidates = self._limit_for_rerank(candidates)

        # ========================================================
        # NO MATCH
        # ========================================================

        if not candidates:

            logger.info(
                "No previous candidates satisfied "
                "the modified search."
            )

            self.search_repository.update_result_count(
                search_id,
                0,
            )

            self.search_repository.update_status(
                search_id,
                "COMPLETED",
            )

            return {
                "search_id": search_id,
                "page": page,
                "page_size": page_size,
                "total_candidates": 0,
                "total_pages": 0,
                "results": [],
            }

        # ========================================================
        # RERANK ONLY THE PREVIOUS CANDIDATES
        # ========================================================

        return self.rerank_candidates(
            search_id=search_id,
            parsed_search=parsed_search,
            job_text=job_text,
            candidates=candidates,
            page=page,
            page_size=page_size,
            conversation_message_id=conversation_message_id,
        )
######
    # Vector Search######

    def vector_search(
        self,
        search_id,
        parsed_search,
        job_text,
        search_embedding,
        job_position_id,
        received_within,
        global_search_allowed,
        page,
        page_size,
        conversation_message_id,
    ):

        logger.info("=" * 80)
        logger.info("ATLAS VECTOR SEARCH")
        logger.info("=" * 80)


        # Atlas Search


        vector_results = (
            self.profile_repository.search_similar_profiles(
                embedding=search_embedding,
                job_position_id=job_position_id,
                received_within=received_within,
                global_search_allowed=global_search_allowed,
            )
        )

        logger.info(
            f"Vector Search returned {len(vector_results)} candidates."
        )


        # Load Candidate Profiles


        candidates = []

        for profile in vector_results:

            profile["semantic_score"] = profile.pop("embedding_score", 0)
            if not job_position_id:
                profile["is_global_profile"] = True
            else:
                profile["is_global_profile"] = (
                    profile.get("job_id") != job_position_id
                )

            candidates.append(profile)

        logger.info(
            f"Loaded {len(candidates)} candidate profiles."
        )
        shortlisted_profile_ids = (
            self.search_repository.get_shortlisted_profile_ids(
                search_id
            )
        )

        candidates = [
            candidate
            for candidate in candidates
            if candidate["profile_id"]
            not in shortlisted_profile_ids
        ]

        logger.info(
            f"After removing shortlisted: {len(candidates)}"
        )


        # No Candidates


        if not candidates:

            logger.warning(
                "No candidates found from vector search."
            )

            self.search_repository.update_result_count(
                search_id,
                0,
            )

            self.search_repository.update_status(
                search_id,
                "COMPLETED",
            )

            return {
                "search_id": search_id,
                "page": page,
                "page_size": page_size,
                "total_candidates": 0,
                "total_pages": 0,
                "results": [],
            }


        # Business Rule Filtering


        logger.info("=" * 80)
        logger.info("BUSINESS RULE FILTERING")
        logger.info("=" * 80)

        logger.info(
            f"Before Filtering : {len(candidates)}"
        )

        candidates = self.candidate_filter_service.filter(

            candidates,

            parsed_search,

        )

        logger.info(
            f"After Filtering : {len(candidates)}"
        )

        candidates = self._limit_for_rerank(candidates)

        # Nothing Left


        if not candidates:

            logger.warning(
                "No candidates remained after filtering."
            )

            self.search_repository.update_result_count(
                search_id,
                0,
            )

            self.search_repository.update_status(
                search_id,
                "COMPLETED",
            )

            return {

                "search_id": search_id,

                "page": page,

                "page_size": page_size,

                "total_candidates": 0,

                "total_pages": 0,

                "results": [],

            }


        # Continue Pipeline


        return self.rerank_candidates(
            search_id=search_id,
            parsed_search=parsed_search,
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
        search_id,
        parsed_search,
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
            search_id=search_id,
            parsed_search=parsed_search,
            candidates=candidates,
            page=page,
            page_size=page_size,
            conversation_message_id=conversation_message_id,
        )
            

######
    # ATS Scoring######

    def score_candidates(
        self,
        search_id,
        parsed_search,
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
            parsed_search.get(
                "required_skills",
                [],
            )
        )


        # Score Each Candidate


        for candidate in candidates:

            # ATS Calculation

            score = self.scoring_service.calculate_score(

                job=parsed_search,

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

            search_id=search_id,

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
        search_id,
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
            search_id=search_id,
            candidates=candidates,
            conversation_message_id=conversation_message_id,
        )


        # Update Job


        self.search_repository.update_result_count(

            search_id,

            total_candidates,

        )

        self.search_repository.update_status(

            search_id,

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

            "search_id": search_id,

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
        search_id: str,
        profile_id: str,
    ):

        logger.info("=" * 80)
        logger.info("CANDIDATE REASONING")
        logger.info("=" * 80)


        # Cache


        cached = self.search_repository.get_reasoning(

            search_id,

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

            candidate = self.search_repository.get_candidate(
                search_id,
                profile_id,
            )

            return {

                "profile_id": profile_id,

                "candidate_name": candidate.get("candidate_name") if candidate else None,

                "reasoning": cached["reasoning"],

                "message": cached["reasoning"],

                "answer": cached["reasoning"],

                "success": True,
            }


        # Candidate


        candidate = self.search_repository.get_candidate(

            search_id,

            profile_id,

        )

        if candidate is None:

            return {

                "message": "Candidate not found."

            }


        # Job


        parsed_search = self.search_repository.get_search(

            search_id,

        )

        if parsed_search is None:

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


        search_context = {

            "title":

                parsed_search.get("title"),

            "experience":

                parsed_search.get("experience"),

            "education":

                parsed_search.get("education"),

            "location":

                parsed_search.get("location"),

            "required_skills":

                parsed_search.get(

                    "required_skills",

                    [],

                ),

            "preferred_skills":

                parsed_search.get(

                    "preferred_skills",

                    [],

                ),

            "excluded_skills":

                parsed_search.get(

                    "excluded_skills",

                    [],

                ),

            "responsibilities":

                parsed_search.get(

                    "responsibilities",

                    [],

                ),

            "qualifications":

                parsed_search.get(

                    "qualifications",

                    [],

                ),

            "nice_to_have":

                parsed_search.get(

                    "nice_to_have",

                    [],

                ),

            "certifications":

                parsed_search.get(

                    "certifications",

                    [],

                ),

        }


        # Prompt


        prompt = build_reasoning_prompt(

            search_context,

            candidate_context,

        )


        # LLM


        reasoning = self.openai_service.generate(

            prompt

        )


        # Save


        self.search_repository.save_reasoning(

            search_id,

            profile_id,

            reasoning,

        )

        logger.info("Reasoning Generated.")

        return {

            "profile_id": profile_id,

            "candidate_name": candidate.get("candidate_name") if candidate else None,

            "reasoning": reasoning,

            "message": reasoning,

            "answer": reasoning,

            "success": True,

        }