from datetime import datetime

from app.repository.base_repository import BaseRepository


class JobVsCandidateRepository(BaseRepository):

    collection_name = "job_vs_candidates"

    def __init__(self):
        super().__init__()
        self.collection = self.db[self.collection_name]
    def save_or_update_candidate_status(
        self,
        job_id: str,
        applicant_id: str,
        profile_id: str,
        is_global_profile: bool,
        status: str,
    ):

        self.collection.update_one(
            {
                "job_id": job_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "applicant_id": applicant_id,
                    "status": status,
                    "is_global_profile": is_global_profile,
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {
                    "job_id": job_id,
                    "profile_id": profile_id,
                    "created_at": datetime.utcnow(),
                },
            },
            upsert=True,
        )

        return True

    def shortlist_candidate(
        self,
        job_id,
        applicant_id,
        profile_id,
        is_global_profile,
    ):
        return self.save_or_update_candidate_status(
            job_id,
            applicant_id,
            profile_id,
            is_global_profile,
            "SHORTLISTED",
        )


    def reject_candidate(
        self,
        job_id,
        applicant_id,
        profile_id,
        is_global_profile,
    ):
        return self.save_or_update_candidate_status(
            job_id,
            applicant_id,
            profile_id,
            is_global_profile,
            "REJECTED",
        )


    def undo_shortlist(
        self,
        job_id,
        applicant_id,
        profile_id,
        is_global_profile,
    ):
        return self.save_or_update_candidate_status(
            job_id,
            applicant_id,
            profile_id,
            is_global_profile,
            "PENDING",
        )


    def undo_reject(
        self,
        job_id,
        applicant_id,
        profile_id,
        is_global_profile,
    ):
        return self.save_or_update_candidate_status(
            job_id,
            applicant_id,
            profile_id,
            is_global_profile,
            "PENDING",
        )


    def get_shortlisted_candidates(
        self,
        job_id,
    ):

        return list(
            self.collection.find(
                {
                    "job_id": job_id,
                    "status": "SHORTLISTED",
                }
            )
        )


    def get_rejected_candidates(
        self,
        job_id,
    ):

        return list(
            self.collection.find(
                {
                    "job_id": job_id,
                    "status": "REJECTED",
                }
            )
        )