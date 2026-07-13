from fastapi import APIRouter
from fastapi import HTTPException
from app.repository.search_repository import SearchRepository
router = APIRouter(
    prefix="/api/cv-service",
    tags=["Candidate Actions"],
)
search_repository = SearchRepository()

# Shortlist Candidate
@router.post(
    "/jd/{job_id}/shortlist/{resume_id}",
)
def shortlist_candidate(
    job_id: str,
    resume_id: str,
):
    try:
        search_repository.shortlist_candidate(
            job_id,
            resume_id,
        )
        return {
            "message": "Candidate shortlisted successfully.",
            "job_id": job_id,
            "resume_id": resume_id,
            "status": "SHORTLISTED",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

# Reject Candidate
@router.post(
    "/reject/{job_id}/{resume_id}",
)
def reject_candidate(
    job_id: str,
    resume_id: str,
):
    try:
        search_repository.reject_candidate(
            job_id,
            resume_id,
        )
        return {
            "message": "Candidate rejected successfully.",
            "job_id": job_id,
            "resume_id": resume_id,
            "status": "REJECTED",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

# Get Shortlisted Candidates
@router.get(
    "/shortlisted/{job_id}",
)
def shortlisted_candidates(
    job_id: str,
):
    try:
        return search_repository.get_shortlisted_candidates(
            job_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

# Get Rejected Candidates
@router.get(
    "/rejected/{job_id}",
)
def rejected_candidates(
    job_id: str,
):
    try:
        return search_repository.get_rejected_candidates(
            job_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )