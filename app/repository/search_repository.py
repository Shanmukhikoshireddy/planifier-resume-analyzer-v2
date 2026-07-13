from datetime import datetime
from bson import ObjectId
from app.repository.base_repository import BaseRepository

class SearchRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.db[
            "search_results"
        ]

    # Save Search Results
    def save_search_results(
        self,
        job_id: str,
        candidates: list,
    ):
        documents = []
        for candidate in candidates:
            documents.append(
                {
                    "job_id": job_id,
                    "resume_id": candidate["resume_id"],
                    "candidate_name": candidate.get(
                        "candidate_name"
                    ),
                    "email": candidate.get(
                        "email"
                    ),
                    "phone": candidate.get(
                        "phone"
                    ),
                    "location": candidate.get(
                        "location"
                    ),
                    "experience": candidate.get(
                        "total_experience"
                    ),
                    "skills": candidate.get(
                        "skills"
                    ),
                    "semantic_score": candidate.get(
                        "semantic_score",
                        0,
                    ),
                    "rerank_score": candidate.get(
                        "rerank_score",
                        0,
                    ),
                    "skill_match_percentage": candidate.get(
                        "skill_match_percentage",
                        0,
                    ),
                    "matched_skills": candidate.get(
                        "matched_skills",
                        [],
                    ),
                    "missing_skills": candidate.get(
                        "missing_skills",
                        [],
                    ),
                    "final_score": candidate.get(
                        "final_score",
                        0,
                    ),
                    "candidate_status": "PENDING",
                    "reasoning_generated": False,
                    "reasoning": candidate.get("reasoning",None),
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
    ):
        return list(
            self.collection.find(
                {"job_id": job_id},
                {"_id": 0}
            ).sort(
                "final_score",
                -1,
            )
        )

    # Get Candidate
    def get_candidate(
        self,
        job_id: str,
        resume_id: str,
    ):
        
        return self.collection.find_one(
        {
            "job_id": job_id,
            "resume_id": resume_id,
        },
        {"_id": 0}
    )

    # Shortlist Candidate
    def shortlist_candidate(
        self,
        job_id: str,
        resume_id: str,
    ):
        self.collection.update_one(
            {
                "job_id": job_id,
                "resume_id": resume_id,
            },
            {
                "$set": {
                    "candidate_status": "SHORTLISTED",
                    "updated_at": datetime.utcnow(),
                }
            }
        )

    # Reject Candidate
    def reject_candidate(
        self,
        job_id: str,
        resume_id: str,
    ):
        self.collection.update_one(
            {
                "job_id": job_id,
                "resume_id": resume_id,
            },
            {
                "$set": {
                    "candidate_status": "REJECTED",
                    "updated_at": datetime.utcnow(),
                }
            }
        )

    # Save AI Reasoning
    def save_reasoning(
        self,
        job_id: str,
        resume_id: str,
        reasoning: str,
    ):
        self.collection.update_one(
            {
                "job_id": job_id,
                "resume_id": resume_id,
            },
            {
                "$set": {
                    "reasoning": reasoning,
                    "reasoning_generated": True,
                    "reasoning_generated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            }
        )

    # Get AI Reasoning
    def get_reasoning(
        self,
        job_id: str,
        resume_id: str,
    ):
        return self.collection.find_one(
            {
                "job_id": job_id,
                "resume_id": resume_id,
            },
            {
                "_id": 0,
                "reasoning": 1,
                "reasoning_generated": 1,
            }
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
        return self.collection.count_documents(
            {"job_id": job_id}
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