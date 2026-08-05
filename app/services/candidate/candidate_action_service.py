from app.repository.search_repository import SearchRepository
from app.config.logging import logger
from app.repository.job_vs_candidate_repository import JobVsCandidateRepository
from app.repository.applicant_repository import ApplicantRepository
class CandidateActionService:

    def __init__(self):

        self.search_repository = SearchRepository()
        self.job_vs_candidate_repository = JobVsCandidateRepository()
        self.applicant_repository = ApplicantRepository()

    ##########################################################
    # Common
    ##########################################################

    def _get_candidate(
        self,
        search_id,
        candidate_name,
    ):

        return self.search_repository.get_candidate_by_name(
            search_id,
            candidate_name,
        )
    
    def _get_candidate_by_profile_id(
        self,
        search_id,
        profile_id,
    ):
        return self.search_repository.get_candidate(
            search_id,
            profile_id,
        )
    
    def _perform_action(
        self,
        candidate,
        search_id,
        search_action,
        job_action,
        applicant_status,
        message,
    ):
        if candidate is None:
            return {
                "success": False,
                "message": "Candidate not found.",
            }

        # Update search_results
        search_action(
            search_id,
            candidate["profile_id"],
        )

        # Update job_vs_candidates
        job_action(
            candidate["job_id"],
            search_id,
            candidate["applicant_id"],
            candidate["profile_id"],
            candidate.get("is_global_profile", False),
        )
        self.applicant_repository.update_status(
            candidate["applicant_id"],
            applicant_status,
        )

        return {
            "success": True,
            "candidate_name": candidate["candidate_name"],
            "profile_id": candidate["profile_id"],
            "message": message.format(
                candidate_name=candidate["candidate_name"]
            ),
        }
    

    def shortlist_by_profile_id(
        self,
        search_id,
        profile_id,
    ):

        candidate = self._get_candidate_by_profile_id(
            search_id,
            profile_id,
        )

        return self._perform_action(
            candidate=candidate,
            search_id=search_id,
            search_action=self.search_repository.shortlist_candidate,
            job_action=self.job_vs_candidate_repository.shortlist_candidate,
            applicant_status="SHORTLISTED",
            message="{candidate_name} shortlisted successfully.",
        )
    
    def reject_by_profile_id(
        self,
        search_id,
        profile_id,
    ):

        candidate = self._get_candidate_by_profile_id(
            search_id,
            profile_id,
        )

        return self._perform_action(
            candidate=candidate,
            search_id=search_id,
            search_action=self.search_repository.reject_candidate,
            job_action=self.job_vs_candidate_repository.reject_candidate,
            applicant_status="REJECTED",
            message="{candidate_name} rejected successfully.",
        )

    def undo_reject_by_profile_id(
        self,
        search_id,
        profile_id,
    ):

        candidate = self._get_candidate_by_profile_id(
            search_id,
            profile_id,
        )

        return self._perform_action(
            candidate=candidate,
            search_id=search_id,
            search_action=self.search_repository.undo_reject,
            job_action=self.job_vs_candidate_repository.undo_reject,
            applicant_status="DRAFT",
            message="{candidate_name} moved back to pending.",
        )

    def undo_shortlist_by_profile_id(
        self,
        search_id,
        profile_id,
    ):

        candidate = self._get_candidate_by_profile_id(
            search_id,
            profile_id,
        )

        return self._perform_action(
            candidate=candidate,
            search_id=search_id,
            search_action=self.search_repository.undo_shortlist,
            job_action=self.job_vs_candidate_repository.undo_shortlist,
            applicant_status="DRAFT",
            message="{candidate_name} moved back to pending.",
        )

    ##########################################################
    # Shortlist
    ##########################################################

    def shortlist(
        self,
        search_id,
        candidate_name,
    ):

        candidate = self._get_candidate(
            search_id,
            candidate_name,
        )

        return self._perform_action(
            candidate=candidate,
            search_id=search_id,
            search_action=self.search_repository.shortlist_candidate,
            job_action=self.job_vs_candidate_repository.shortlist_candidate,
            applicant_status="SHORTLISTED",
            message="{candidate_name} shortlisted successfully.",
        )

    ##########################################################
    # Reject
    ##########################################################

    def reject(
        self,
        search_id,
        candidate_name,
    ):

        candidate = self._get_candidate(
            search_id,
            candidate_name,
        )

        return self._perform_action(
            candidate=candidate,
            search_id=search_id,
            search_action=self.search_repository.reject_candidate,
            job_action=self.job_vs_candidate_repository.reject_candidate,
            applicant_status="REJECTED",
            message="{candidate_name} rejected successfully.",
        )

    ##########################################################
    # Show Shortlisted
    ##########################################################

    def shortlisted(
        self,
        search_id,
    ):

        results = self.search_repository.get_shortlisted_candidates(
            search_id
        )
        if not results:
            return {
                "search_id": search_id,
                "total_candidates": 0,
                "message": "No shortlisted candidates found.",
                "results": [],
            }

        return {
            "search_id": search_id,
            "total_candidates": len(results),
            "results": results,
        }
        
    

    ##########################################################
    # Show Rejected
    ##########################################################

    def rejected(
        self,
        search_id,
    ):

        results=self.search_repository.get_rejected_candidates(
            search_id
        )
        if not results:
            return {
                "search_id": search_id,
                "total_candidates": 0,
                "message": "No rejected candidates found.",
                "results": [],
            }

        return {
            "search_id": search_id,
            "total_candidates": len(results),
            "results": results,
        }
    

    def undo_shortlist(
        self,
        search_id,
        candidate_name,
    ):

        candidate = self._get_candidate(
            search_id,
            candidate_name,
        )

        return self._perform_action(
            candidate=candidate,
            search_id=search_id,
            search_action=self.search_repository.undo_shortlist,
            job_action=self.job_vs_candidate_repository.undo_shortlist,
            applicant_status="DRAFT",
            message="{candidate_name} moved back to pending.",
        )


    def undo_reject(
        self,
        search_id,
        candidate_name,
    ):

        candidate = self._get_candidate(
            search_id,
            candidate_name,
        )

        return self._perform_action(
            candidate=candidate,
            search_id=search_id,
            search_action=self.search_repository.undo_reject,
            job_action=self.job_vs_candidate_repository.undo_reject,
            applicant_status="DRAFT",
            message="{candidate_name} moved back to pending.",
        )