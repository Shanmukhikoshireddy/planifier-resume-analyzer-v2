from fastapi import APIRouter
from app.config.mongo import db
from app.repository.minio_repository import MinioRepository
from app.services.shared.openai_service import OpenAIService
from app.services.ingestion.embedding_service import EmbeddingService
router = APIRouter(
    prefix="/api/cv-service/health",
    tags=["Health"],
)
@router.get("")
def health_check():
    status = {}

    # MongoDB
    try:
        db.command("ping")
        status["mongodb"] = "UP" 
    except Exception as e:
        status["mongodb"] = f"DOWN : {str(e)}"

    # MinIO
    try:
        minio = MinioRepository()
        if minio.bucket_exists():
            status["minio"] = "UP"
        else:
            status["minio"] = "Bucket Not Found"
    except Exception as e:
        status["minio"] = f"DOWN : {str(e)}"

    # OpenAI
    try:
        openai = OpenAIService()
        if openai.health_check():
            status["openai"] = "UP"
        else:
            status["openai"] = "DOWN"
    except Exception as e:
        status["openai"] = f"DOWN : {str(e)}"
    # Embedding Model
    try:
        EmbeddingService()
        status["embedding_model"] = "UP"
    except Exception as e:
        status["embedding_model"] = f"DOWN : {str(e)}"
        
    # Overall Status

    overall = "HEALTHY"
    for value in status.values():
        if not value.startswith(
            "UP"
        ):
            overall = "UNHEALTHY"
            break
    return {
        "service": "Planifier Resume Analyzer",
        "version": "1.0.0",
        "status": overall,
        "components": status,
    }