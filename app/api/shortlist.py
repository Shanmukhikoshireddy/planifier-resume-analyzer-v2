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
    "/jod/{job_id}/profile/{profile_id}",
)
def shortlist_candidate(
    job_id: str,
    profile_id: str,
):
    try:

        response = candidate_action_service.shortlist_by_profile_id(
            job_id=job_id,
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
    "/job/{job_id}/profile/{profile_id}",
)
def reject_candidate(
    job_id: str,
    profile_id: str,
):
    try:

        response = candidate_action_service.reject_by_profile_id(
            job_id=job_id,
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
    "/shortlisted/job/{job_id}",
)
def shortlisted_candidates(
    job_id: str,
):
    try:
        return candidate_action_service.shortlisted(job_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    
    

# Get Rejected Candidates
@router.get(
    "/rejected/job/{job_id}",
)
def rejected_candidates(
    job_id: str,
):
    try:
        return candidate_action_service.rejected(job_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    

@router.post(
    "/unshortlist/job/{job_id}/profile/{profile_id}",
)
def unshortlist_candidate(
    job_id: str,
    profile_id: str,
):
    try:

        response = candidate_action_service.undo_shortlist_by_profile_id(
            job_id=job_id,
            profile_id=profile_id,
        )

        return response

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    

@router.post(
    "/unreject/job/{job_id}/profile/{profile_id}",
)
def unreject_candidate(
    job_id: str,
    profile_id: str,
):
    try:

        response = candidate_action_service.undo_reject_by_profile_id(
            job_id=job_id,
            profile_id=profile_id,
        )

        return response

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )