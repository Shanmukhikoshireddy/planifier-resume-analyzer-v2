from fastapi import APIRouter
from fastapi import HTTPException
from app.repository.profile_repository import ProfileRepository
from app.repository.minio_repository import MinioRepository

router = APIRouter(
    prefix="/api/cv-service/resume",
    tags=["Resume"],
)
profile_repository = ProfileRepository()
minio_repository = MinioRepository()

# Get Resume Profile
@router.get("/{profile_id}")
def get_resume(
    profile_id: str,
):
    profile = profile_repository.get_profile(
        profile_id
    )
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found.",
        )
    resume_url = minio_repository.get_presigned_url(
        profile["resume_path"]
    )
    return {
        "profile_id": profile_id,
        "candidate_name": profile.get("candidate_name"),
        "file_name": profile.get("file_name"),
        "resume_url": resume_url,
    }

# List All Resumes
@router.get("/",)
def get_resumes():
    return profile_repository.get_all_profiles()


# Download Resume
@router.get("/download/{profile_id}")
def download_resume(
    profile_id: str,
):
    profile = profile_repository.get_profile(
        profile_id
    )
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found.",
        )
    download_url = minio_repository.get_presigned_url(

        profile["resume_path"],

        download=True,

    )

    return {

        "download_url": download_url

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