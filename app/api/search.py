from fastapi import APIRouter
from fastapi import HTTPException
from app.dto.request.search_request import SearchRequest
from app.services.search.search_service import SearchService
import traceback
from app.config.logging import logger
from app.repository.search_repository import SearchRepository
from app.repository.job_repository import JobRepository

router = APIRouter(
    prefix="/api/cv-service/search",
    tags=["Candidate Search"],
)
search_service = SearchService()
search_repository = SearchRepository()
job_repository = JobRepository()

# Search History
@router.get(
    "/feed",
)
def search_history():
    return job_repository.get_all_jobs()

# Search Candidates
from fastapi import Query
@router.post("")
def search_candidates(
    request: SearchRequest,
    page: int = Query(
        default=1,
        ge=1,
        description="Page Number"
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Candidates Per Page"
    ),
):
    try:
        return search_service.search(
            job_position=request.job_position,
            job_description=request.job_description,
            received_within=request.received_within,
            page=page,
            page_size=page_size,
        )
    except Exception as e: 
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

# Get Search Results
@router.get(
    "/job/{job_id}/all",
)
def get_search_results(
    job_id: str,
):
    results = search_repository.get_search_results(
        job_id
    )
    if len(results) == 0:
        raise HTTPException(
            status_code=404,
            detail="Search Results Not Found.",
        )
    return {
        "job_id": job_id,
        "total_candidates": len(results),
        "results": results,
    }

# Candidate Reasoning
@router.get(
    "/reasoning/{job_id}/{resume_id}",
)
def get_reasoning(
    job_id: str,
    resume_id: str,
):
    try:
        return search_service.get_candidate_reasoning(
            job_id,
            resume_id,
        )
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


