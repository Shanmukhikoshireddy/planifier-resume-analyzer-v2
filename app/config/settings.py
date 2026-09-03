
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):

    # FastAPI
    APP_NAME: str = "Planifier Resume Analyzer"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    DEBUG: bool = True
    # Used behind reverse proxy on 175.101.46.170 → api.edpedia.co
    ROOT_PATH: str = "/v1.0/planifier/cv-analysis"
    # Comma-separated frontend origins
    CORS_ORIGINS: str = (
        "https://planifier.app,"
        "https://www.planifier.app,"
        "https://app.planifier.app,"
        "https://planifier-app.netlify.app,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:3001,"
        "http://localhost:5173"
    )

    UPLOAD_DIR: str = "uploads"
    EXTRACT_DIR: str = "uploads/extracted"
    TEMP_DIR: str = "temp"

#     # MongoDB
    MONGODB_URI: str
    MONGODB_DATABASE: str

    MONGODB_AI_URI: str
    MONGODB_AI_DATABASE: str
 
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4.1"

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    VECTOR_SEARCH_LIMIT: int = 80
    VECTOR_SEARCH_CANDIDATES: int = 200
    RERANK_TOP_K: int = 20
    RERANK_MAX_CHARS: int = 800
    SEMANTIC_WEIGHT: float = 0.35
    SKILL_WEIGHT: float = 0.25
    EXPERIENCE_WEIGHT: float = 0.15
    EDUCATION_WEIGHT: float = 0.10
    CERTIFICATION_WEIGHT: float = 0.05
    RERANK_WEIGHT: float = 0.10

    # Scheduler (seconds)
    SCHEDULER_INTERVAL: int = 3000

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings():
    return Settings()


print("Current Working Directory:", Path.cwd())
print(".env Exists:", Path(".env").exists())
settings = get_settings()
 