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
from app.prompts.job_prompt import build_job_prompt
from app.prompts.reasoning_prompt import build_reasoning_prompt
import re
import json
class SearchService:
    def __init__(self):
        self.job_repository = JobRepository()
        self.search_repository = SearchRepository()
        self.embedding_repository = EmbeddingRepository()
        self.profile_repository = ProfileRepository()
        self.openai_service = OpenAIService()
        self.embedding_service = EmbeddingService()
        self.cache_service = CacheService()
        self.reranker_service = RerankerService()
        self.scoring_service = ScoringService()

    # Search
    def search(
        self,
        job_position: str,
        job_description: str,
        received_within: str,
        page: int,
        page_size: int,
    ):
        logger.info("Starting Candidate Search.")
        logger.info("RAW JOB DESCRIPTION")
        logger.info(job_description)
        prompt = build_job_prompt(job_description)
        job = self.openai_service.generate_json(
            prompt
        )
        logger.info("RAW PARSED JOB")
        logger.info(job)

        # Validate Response
        if not isinstance(job, dict):
            raise ValueError(
                "OpenAI did not return a JSON object."
            )

        if not job:
            raise ValueError(
                "Parsed job is empty."
            )

        # Ensure Required Keys Exist
        job.setdefault("title", "")
        job.setdefault("experience", "")
        job.setdefault("education", "")
        job.setdefault("skills", [])
        job.setdefault("certifications", [])
        job.setdefault("responsibilities", [])
        job.setdefault("qualifications", [])
        job.setdefault("nice_to_have", [])
        logger.info("FINAL JOB")
        logger.info(job)

        if not job["title"]:
            logger.warning(
                "No title extracted from Job Description."
            )
        if not job["skills"]:
            logger.warning(
                "No skills extracted from Job Description."
            )
        logger.info(
            "Job Parsed Successfully."
        )

        # Continue Search
        return self.process_job(
            job=job,
            job_position=job_position,
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
        sections = [
            job.get("title","",),
            job.get("experience","",),
            job.get("education","",),
            " ".join(job.get("skills",[],)),
            " ".join(job.get("responsibilities",[],)),
            " ".join(job.get("qualifications",[],)),
            " ".join(job.get("nice_to_have",[],)),
        ]
        return "\n".join([
                section
                for section in sections
                if section
            ]
        )

    # Process Job
    def process_job(
        self,
        job: dict,
        job_position: str,
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
            profile = self.profile_repository.get_profile(result["resume_id"])
            if profile is None:
                continue
            profile["semantic_score"] = result.get("embedding_score",0,)
            candidates.append(profile)
        logger.info(f"Loaded {len(candidates)} candidate profiles.")
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
    def normalize_skill(
        self,
        skill: str,
    ) -> str:
        if not skill:
            return ""
        # Lowercase + Trim
        skill = skill.lower().strip()
        # Remove spaces, -, _, .
        skill = re.sub(
            r"[\s\-_\.]+",
            "",
            skill,
        )
        synonyms = {
            # FastAPI
            "fastapi": "fastapi",
            "fastapiframework": "fastapi",
            # JavaScript
            "js": "javascript",
            "javascript": "javascript",
            # Node
            "node": "nodejs",
            "nodejs": "nodejs",
            # React
            "reactjs": "react",
            "react": "react",
            # MongoDB
            "mongodb": "mongodb",
            "mongodbatlas": "mongodbatlas",
            # PostgreSQL
            "postgres": "postgresql",
            "postgresql": "postgresql",
            # AI / ML
            "ml": "machinelearning",
            "machinelearning": "machinelearning",
            "ai": "artificialintelligence",
            "artificialintelligence": "artificialintelligence",
            # NLP
            "naturallanguageprocessing": "nlp",
            "nlp": "nlp",
            # Vector Search
            "vectorsearch": "vectorsearch",
            # Retrieval Augmented Generation
            "rag": "rag",
            "retrievalaugmentedgeneration": "rag",
            # Large Language Models
            "llm": "llm",
            "large languagemodels": "llm",
            "llmapplications": "llm",
            # Hugging Face
            "huggingface": "huggingface",
            "huggingfacetransformers": "huggingface",
            # REST
            "restapi": "restapi",
            "restapis": "restapi",
        }
        return synonyms.get(
            skill,
            skill,
        )
    # Score Candidates
    def score_candidates(
        self,
        job_id: str,
        job: dict,
        candidates: list,
        page: int,
        page_size: int,
    ):
        logger.info(
            "Calculating ATS Scores..."
        )
        required_skills = [
            self.normalize_skill(skill)
            for skill in job.get(
                "skills",
                [],
            )
        ]
        required_years = self.scoring_service.extract_years(
            job.get(
                "experience",
                "",
            )
        )
        required_education = job.get(
            "education",
            "",
        ).lower()
        required_certifications = {
            cert.lower()
            for cert in job.get(
                "certifications",
                [],
            )
        }
        scored_candidates = []
        
        for candidate in candidates:
            logger.info(type(candidate.get("education")))
            logger.info(type(candidate.get("projects")))
            logger.info(type(candidate.get("certifications")))
            # Skills
            candidate_skills = [
                self.normalize_skill(skill)
                for skill in candidate.get(
                    "skills",
                    [],
                )
            ]
            matched_skills = []

            missing_skills = []

            for skill in job.get("skills", []):

                normalized = self.normalize_skill(skill)

                if normalized in candidate_skills:

                    matched_skills.append(skill)

                else:

                    missing_skills.append(skill)
            if required_skills:
                skill_match_percentage = round((len(matched_skills)/len(required_skills))* 100,2,)
            else:
                skill_match_percentage = 100

            # Experience
            try:
                candidate_years = float(
                    candidate.get("experience_years",0,))
            except Exception:
                candidate_years = 0

            # Education
            candidate_education = self.list_to_text(
                candidate.get(
                    "education",
                    [],
                )
            ).lower()

            education_match = (
                required_education in candidate_education
                if required_education
                else True
            )

            # Certifications
            candidate_certifications = {
                cert.lower()
                for cert in candidate.get("certifications",[],)
            }

            certification_match = bool(
                required_certifications.intersection(candidate_certifications))

            # Final Score
            final_score = self.scoring_service.final_score(
                similarity_score=candidate.get("semantic_score",0,),
                rerank_score=candidate.get("rerank_score",0,),
                matched_skills=matched_skills,
                required_skills=required_skills,
                candidate_years=candidate_years,
                required_years=required_years,
                education_match=education_match,
                certification_match=certification_match,
            )

            candidate["matched_skills"] = matched_skills
            candidate["missing_skills"] = missing_skills
            candidate["skill_match_percentage"] = skill_match_percentage
            candidate["final_score"] = round(final_score,2,)
            scored_candidates.append(
                candidate
            )

        # Sort Candidate
        scored_candidates.sort(key=lambda x: x["final_score"],reverse=True,)
        total_candidates = len(scored_candidates)
        total_pages = (total_candidates + page_size - 1) // page_size
        logger.info(
            "ATS Scoring Completed."
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
            "skills": job.get("skills",[],),
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