from fastapi import APIRouter
from fastapi import APIRouter, HTTPException
from app.repository.profile_repository import ProfileRepository

router = APIRouter(
    prefix="/api/cv-service/resume",
    tags=["Resume"],
)

profile_repository = ProfileRepository()

@router.get("/{profile_id}")
def get_resume(
    profile_id: str,
):
    profile = profile_repository.get_profile(profile_id)

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found.",
        )

    return {
        "profile_id": profile_id,
        "candidate_name": profile.get("candidate_name"),
        "file_name": profile.get("file_name"),
        "resume_url": profile.get("resume_path"),
    }
# List All Resumes
@router.get("/",)
def get_resumes():
    return profile_repository.get_all_profiles()

#download
@router.get("/download/{profile_id}")
def download_resume(
    profile_id: str,
):
    profile = profile_repository.get_profile(profile_id)

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found.",
        )

    return {
        "download_url": profile.get("resume_path")
    }
# Soft Delete Resume
@router.delete("/{profile_id}",)

def delete_resume(profile_id: str,):
    updated = profile_repository.soft_delete_profile(
        profile_id
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Resume not found.",
        )
    return {
        "message": "Resume deleted successfully."
    }