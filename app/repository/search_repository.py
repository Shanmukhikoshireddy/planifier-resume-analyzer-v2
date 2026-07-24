from datetime import datetime
from bson import ObjectId
from app.repository.base_repository import BaseRepository
import re
from app.config.logging import logger
from app.repository.job_repository import JobRepository

class SearchRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.db[
            "search_results"
        ]
        self.job_repository = JobRepository()
        

    # Save Search Results
    def save_search_results(
        self,
        job_id: str,
        candidates: list,
        conversation_message_id=None,
    ):
        documents = []

        for candidate in candidates:

            documents.append(
                {
                    "job_id": job_id,
                    "conversation_message_id": conversation_message_id,

                    "profile_id": candidate.get("profile_id"),

                    "candidate_name": candidate.get("candidate_name"),

                    "email": candidate.get("email"),

                    "phone": candidate.get("phone"),

                    "location": candidate.get("location"),

                    "designation": candidate.get("designation"),

                    "job_position": candidate.get("job_position"),

                    "current_company": candidate.get("current_company"),

                    "experience": candidate.get("total_experience"),

                    "experience_years": candidate.get("experience_years"),

                    "summary": candidate.get("summary"),

                    "skills": candidate.get(
                        "skills",
                        [],
                    ),

                    "education": candidate.get(
                        "education",
                        [],
                    ),

                    "projects": candidate.get(
                        "projects",
                        [],
                    ),

                    "certifications": candidate.get(
                        "certifications",
                        [],
                    ),

                    "resume_text": candidate.get(
                        "resume_text",
                    ),

                    ####################################################
                    # Search Scores
                    ####################################################

                    "semantic_score":
                        candidate.get(
                            "semantic_score",
                            0,
                        ) * 100,

                    "rerank_score":
                        candidate.get(
                            "rerank_score",
                            0,
                        ) * 100,

                    "skill_match_percentage":
                        candidate.get(
                            "skill_match_percentage",
                            0,
                        ),

                    "matched_skills":
                        candidate.get(
                            "matched_skills",
                            [],
                        ),

                    "missing_skills":
                        candidate.get(
                            "missing_skills",
                            [],
                        ),

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

                    "score_breakdown":
                        candidate.get(
                            "score_breakdown",
                            {},
                        ),

                    "match_level":
                        candidate.get(
                            "match_level",
                        ),

                    "final_score":
                        candidate.get(
                            "final_score",
                            0,
                        ),

                    ####################################################
                    # Candidate Status
                    ####################################################

                    "candidate_status": "PENDING",

                    ####################################################
                    # AI Reasoning
                    ####################################################

                    "reasoning_generated": False,

                    "reasoning": None,

                    ####################################################
                    # Audit
                    ####################################################

                    "created_at": datetime.utcnow(),

                    "updated_at": datetime.utcnow(),
                }
            )

        if documents:

            self.collection.insert_many(
                documents
            )

    # Get Search Results
    def get_search_results(
        self,
        job_id: str,
        conversation_message_id: str = None,
    ):
        if conversation_message_id:
            search_id = conversation_message_id
        else:
            search_id = self.job_repository.get_latest_search_id(job_id)

        if not search_id:
            return []

        return list(
            self.collection.find(
                {
                    "job_id": job_id,
                    "conversation_message_id": search_id,
                },
                {
                    "_id": 0,
                },
            ).sort(
                "final_score",
                -1,
            )
        )

    # Get Candidate
    def get_candidate(
        self,
        job_id: str,
        profile_id: str,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        if not latest_search_id:
            return None

        return self.collection.find_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "profile_id": profile_id,
            },
            {
                "_id": 0,
            },
        )

    # Shortlist Candidate
    def shortlist_candidate(
        self,
        job_id: str,
        profile_id: str,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        self.collection.update_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "candidate_status": "SHORTLISTED",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    # Reject Candidate
    def reject_candidate(
        self,
        job_id: str,
        profile_id: str,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        self.collection.update_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "candidate_status": "REJECTED",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        
    # Save AI Reasoning
    def save_reasoning(
        self,
        job_id,
        profile_id,
        reasoning,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        self.collection.update_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "reasoning": reasoning,
                    "reasoning_generated": True,
                    "reasoning_generated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    # Get AI Reasoning
    def get_reasoning(
        self,
        job_id,
        profile_id,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        if not latest_search_id:
            return None

        return self.collection.find_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "profile_id": profile_id,
            },
            {
                "_id": 0,
                "reasoning": 1,
                "reasoning_generated": 1,
            },
        )

    # Delete Search Results
    def delete_search_results(
        self,
        job_id: str,
    ):
        self.collection.delete_many(
            {"job_id": job_id}
        )

    # Count Search Results
    def count_results(
        self,
        job_id: str,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        if not latest_search_id:
            return 0

        return self.collection.count_documents(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
            }
        )
    
    # Get Shortlisted Candidates
    def get_shortlisted_candidates(
        self,
        job_id: str,
    ):
        return list(
            self.collection.find(
                {
                    "job_id": job_id,
                    "candidate_status": "SHORTLISTED",
                },
                {"_id": 0,},
            ).sort(
                "final_score",
                -1,
            )
        )

    # Get Rejected Candidates
    def get_rejected_candidates(
        self,
        job_id: str,
    ):
        return list(
            self.collection.find(
                {
                    "job_id": job_id,
                    "candidate_status": "REJECTED",
                },
                {"_id": 0,},
            ).sort(
                "final_score",
                -1,
            )
        )

    def get_candidate_by_name(
        self,
        job_id,
        candidate_name,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        if not latest_search_id:
            return None

        candidate = self.collection.find_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "candidate_name": {
                    "$regex": f"^{re.escape(candidate_name)}$",
                    "$options": "i",
                },
            }
        )

        if candidate:
            return candidate

        return self.collection.find_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "candidate_name": {
                    "$regex": re.escape(candidate_name),
                    "$options": "i",
                },
            }
        )
    
    def undo_shortlist(
        self,
        job_id,
        profile_id,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        self.collection.update_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "candidate_status": "PENDING",
                    "updated_at": datetime.utcnow(),
                }
            },
        )


    def undo_reject(
        self,
        job_id,
        profile_id,
    ):
        latest_search_id = self.job_repository.get_latest_search_id(job_id)

        self.collection.update_one(
            {
                "job_id": job_id,
                "conversation_message_id": latest_search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "candidate_status": "PENDING",
                    "updated_at": datetime.utcnow(),
                }
            },
        )


    


    # Get Search Results By Conversation Message
    def get_results_by_conversation_message(
        self,
        conversation_message_id: str,
    ):
        return list(
            self.collection.find(
                {
                    "conversation_message_id": conversation_message_id,
                },
                {
                    "_id": 0,
                },
            ).sort(
                "final_score",
                -1,
            )
        )