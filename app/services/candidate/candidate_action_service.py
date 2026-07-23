from app.repository.search_repository import SearchRepository
from app.config.logging import logger

class CandidateActionService:

    def __init__(self):

        self.search_repository = SearchRepository()

    ##########################################################
    # Common
    ##########################################################

    def _get_candidate(
        self,
        job_id,
        candidate_name,
    ):

        return self.search_repository.get_candidate_by_name(
            job_id,
            candidate_name,
        )
    
    def _get_candidate_by_profile_id(
        self,
        job_id,
        profile_id,
    ):
        return self.search_repository.get_candidate(
            job_id,
            profile_id,
        )
    
    def _perform_action(
        self,
        candidate,
        job_id,
        action,
        message,
    ):
        """
        Common helper for candidate actions.
        """

        if candidate is None:
            return {
                "success": False,
                "message": "Candidate not found.",
            }

        action(
            job_id,
            candidate["profile_id"],
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
        job_id,
        profile_id,
    ):

        candidate = self._get_candidate_by_profile_id(
            job_id,
            profile_id,
        )

        return self._perform_action(
            candidate=candidate,
            job_id=job_id,
            action=self.search_repository.shortlist_candidate,
            message="{candidate_name} shortlisted successfully.",
        )
    
    def reject_by_profile_id(
        self,
        job_id,
        profile_id,
    ):

        candidate = self._get_candidate_by_profile_id(
            job_id,
            profile_id,
        )

        return self._perform_action(
            candidate=candidate,
            job_id=job_id,
            action=self.search_repository.reject_candidate,
            message="{candidate_name} rejected successfully.",
        )
    

    def undo_shortlist_by_profile_id(
        self,
        job_id,
        profile_id,
    ):

        candidate = self._get_candidate_by_profile_id(
            job_id,
            profile_id,
        )

        return self._perform_action(
            candidate=candidate,
            job_id=job_id,
            action=self.search_repository.undo_shortlist,
            message="{candidate_name} removed from shortlist successfully.",
        )
    

    def undo_reject_by_profile_id(
        self,
        job_id,
        profile_id,
    ):

        candidate = self._get_candidate_by_profile_id(
            job_id,
            profile_id,
        )

        return self._perform_action(
            candidate=candidate,
            job_id=job_id,
            action=self.search_repository.undo_reject,
            message="{candidate_name} restored successfully.",
        )

    ##########################################################
    # Shortlist
    ##########################################################

    def shortlist(
        self,
        job_id,
        candidate_name,
    ):

        candidate = self._get_candidate(
            job_id,
            candidate_name,
        )

        return self._perform_action(
            candidate=candidate,
            job_id=job_id,
            action=self.search_repository.shortlist_candidate,
            message="{candidate_name} shortlisted successfully.",
        )

    ##########################################################
    # Reject
    ##########################################################

    def reject(
        self,
        job_id,
        candidate_name,
    ):

        candidate = self._get_candidate(
            job_id,
            candidate_name,
        )

        return self._perform_action(
            candidate=candidate,
            job_id=job_id,
            action=self.search_repository.reject_candidate,
            message="{candidate_name} rejected successfully.",
        )

    ##########################################################
    # Show Shortlisted
    ##########################################################

    def shortlisted(
        self,
        job_id,
    ):

        return self.search_repository.get_shortlisted_candidates(
            job_id
        )

    ##########################################################
    # Show Rejected
    ##########################################################

    def rejected(
        self,
        job_id,
    ):

        return self.search_repository.get_rejected_candidates(
            job_id
        )
    

    def undo_shortlist(
        self,
        job_id,
        candidate_name,
    ):

        candidate = self._get_candidate(
            job_id,
            candidate_name,
        )

        return self._perform_action(
            candidate=candidate,
            job_id=job_id,
            action=self.search_repository.undo_shortlist,
            message="{candidate_name} removed from shortlist successfully.",
        )


    def undo_reject(
        self,
        job_id,
        candidate_name,
    ):

        candidate = self._get_candidate(
            job_id,
            candidate_name,
        )

        return self._perform_action(
            candidate=candidate,
            job_id=job_id,
            action=self.search_repository.undo_reject,
            message="{candidate_name} restored successfully.",
        )