from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):

    # FastAPI
    APP_NAME: str = "Planifier Resume Analyzer"
    APP_VERSION: str = "1.0.0"
    UPLOAD_DIR: str = "uploads"
    EXTRACT_DIR: str = "uploads/extracted"
    TEMP_DIR: str = "temp"
    DEBUG: bool = True

    # MongoDB
    MONGODB_URI: str
    MONGODB_DATABASE: str

    # MinIO
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    MINIO_SECURE: bool = False

    # OpenAI
    OPENAI_API_KEY: str 
    OPENAI_MODEL: str = "gpt-5"

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    SEMANTIC_WEIGHT: float  = 0.35
    SKILL_WEIGHT: float  = 0.25
    EXPERIENCE_WEIGHT: float  = 0.15
    EDUCATION_WEIGHT: float  = 0.10
    CERTIFICATION_WEIGHT: float  = 0.05
    RERANK_WEIGHT: float = 0.10
    OPENAI_API_KEY: str
    OPENAI_MODEL: str
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # Scheduler
    SCHEDULER_INTERVAL: int = 3000
@lru_cache
def get_settings():
    return Settings()


print("Current Working Directory:", Path.cwd())
print(".env Exists:", Path(".env").exists())
settings = get_settings()