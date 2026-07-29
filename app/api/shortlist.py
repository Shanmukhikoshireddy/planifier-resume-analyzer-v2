from fastapi import APIRouter
from fastapi import HTTPException
from app.services.candidate.candidate_action_service import (
    CandidateActionService,
)
router = APIRouter(
    prefix="/api/cv-service",
    tags=["Candidate Actions"],
)
candidate_action_service = CandidateActionService()

# Shortlist Candidate
@router.post(
    "/jod/{search_id}/profile/{profile_id}",
)
def shortlist_candidate(
    search_id: str,
    profile_id: str,
):
    try:

        response = candidate_action_service.shortlist_by_profile_id(
            search_id=search_id,
            profile_id=profile_id,
        )

        return response

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

# Reject Candidate
@router.post(
    "/job/{search_id}/profile/{profile_id}",
)
def reject_candidate(
    search_id: str,
    profile_id: str,
):
    try:

        response = candidate_action_service.reject_by_profile_id(
            search_id=search_id,
            profile_id=profile_id,
        )

        return response

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

# Get Shortlisted Candidates
@router.get(
    "/shortlisted/job/{search_id}",
)
def shortlisted_candidates(
    search_id: str,
):
    try:
        return candidate_action_service.shortlisted(search_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    
    

# Get Rejected Candidates
@router.get(
    "/rejected/job/{search_id}",
)
def rejected_candidates(
    search_id: str,
):
    try:
        return candidate_action_service.rejected(search_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    

@router.post(
    "/unshortlist/job/{search_id}/profile/{profile_id}",
)
def unshortlist_candidate(
    search_id: str,
    profile_id: str,
):
    try:

        response = candidate_action_service.undo_shortlist_by_profile_id(
            search_id=search_id,
            profile_id=profile_id,
        )

        return response

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    

@router.post(
    "/unreject/job/{search_id}/profile/{profile_id}",
)
def unreject_candidate(
    search_id: str,
    profile_id: str,
):
    try:

        response = candidate_action_service.undo_reject_by_profile_id(
            search_id=search_id,
            profile_id=profile_id,
        )

        return response

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )