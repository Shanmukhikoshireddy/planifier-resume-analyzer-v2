from datetime import datetime
from app.utils.datetime_utils import utc_now
from app.repository.base_repository import BaseRepository


class JobVsCandidateRepository(BaseRepository):

    collection_name = "job_vs_candidates"

    def __init__(self):
        super().__init__()
        self.collection = self.db[self.collection_name]

    ##########################################################
    # Common Save / Update
    ##########################################################

    def save_or_update_candidate_status(
        self,
        job_id: str,
        search_id: str,
        applicant_id: str,
        profile_id: str,
        is_global_profile: bool,
        status: str,
    ):

        self.collection.update_one(
            {
                "job_id": job_id,
                "search_id": search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "applicant_id": applicant_id,
                    "status": status,
                    "is_global_profile": is_global_profile,
                    "updated_at": utc_now(),
                },
                "$setOnInsert": {
                    "job_id": job_id,
                    "search_id": search_id,
                    "profile_id": profile_id,
                    "created_at": utc_now(),
                },
            },
            upsert=True,
        )

        return True

    ##########################################################
    # Shortlist
    ##########################################################

    def shortlist_candidate(
        self,
        job_id,
        search_id,
        applicant_id,
        profile_id,
        is_global_profile,
    ):
        return self.save_or_update_candidate_status(
            job_id=job_id,
            search_id=search_id,
            applicant_id=applicant_id,
            profile_id=profile_id,
            is_global_profile=is_global_profile,
            status="SHORTLISTED",
        )

    ##########################################################
    # Reject
    ##########################################################

    def reject_candidate(
        self,
        job_id,
        search_id,
        applicant_id,
        profile_id,
        is_global_profile,
    ):
        return self.save_or_update_candidate_status(
            job_id=job_id,
            search_id=search_id,
            applicant_id=applicant_id,
            profile_id=profile_id,
            is_global_profile=is_global_profile,
            status="REJECTED",
        )

    ##########################################################
    # Undo Shortlist
    ##########################################################

    def undo_shortlist(
        self,
        job_id,
        search_id,
        applicant_id,
        profile_id,
        is_global_profile,
    ):
        return self.save_or_update_candidate_status(
            job_id=job_id,
            search_id=search_id,
            applicant_id=applicant_id,
            profile_id=profile_id,
            is_global_profile=is_global_profile,
            status="PENDING",
        )

    ##########################################################
    # Undo Reject
    ##########################################################

    def undo_reject(
        self,
        job_id,
        search_id,
        applicant_id,
        profile_id,
        is_global_profile,
    ):
        return self.save_or_update_candidate_status(
            job_id=job_id,
            search_id=search_id,
            applicant_id=applicant_id,
            profile_id=profile_id,
            is_global_profile=is_global_profile,
            status="PENDING",
        )

    ##########################################################
    # Get Shortlisted Candidates
    ##########################################################

    def get_shortlisted_candidates(
        self,
        search_id,
    ):

        results = list(
            self.collection.find(
                {
                    "search_id": search_id,
                    "status": "SHORTLISTED",
                }
            )
        )

        for result in results:
            result["_id"] = str(result["_id"])

        return results

    ##########################################################
    # Get Rejected Candidates
    ##########################################################

    def get_rejected_candidates(
        self,
        search_id,
    ):

        results = list(
            self.collection.find(
                {
                    "search_id": search_id,
                    "status": "REJECTED",
                }
            )
        )

        for result in results:
            result["_id"] = str(result["_id"])

        return results