from sentence_transformers import SentenceTransformer
from app.config.settings import settings
from app.config.logging import logger

class EmbeddingService:
    """
    Generic Embedding Service.
    Responsible only for converting text into embeddings.
    Used by:
        • Resume Embeddings
        • Job Embeddings
        • Future Semantic Search
    """
    _model = None
    def __init__(self):
        if EmbeddingService._model is None:
            logger.info(
                f"Loading Embedding Model : {settings.EMBEDDING_MODEL}"
            )
            EmbeddingService._model = SentenceTransformer(
                settings.EMBEDDING_MODEL
            )
            logger.info(
                "Embedding model loaded."
            )
        self.model = EmbeddingService._model

    # Generate Embedding
    def generate_embedding(
        self,
        text: str,
    ) -> list[float]:
        logger.info(
            "Generating embedding..."
        )
        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
        )
        logger.info(
            "Embedding generated."
        )
        return embedding.tolist()

    # Batch Embeddings
    def generate_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        logger.info(
            f"Generating {len(texts)} embeddings..."
        )
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
        )
        return [
            embedding.tolist()
            for embedding in embeddings
        ]