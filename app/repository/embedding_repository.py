from datetime import datetime, timedelta
from app.repository.base_repository import BaseRepository

class EmbeddingRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.db["embeddings"]
    # Save Embedding
    def save_embedding(
        self,
        resume_id: str,
        embedding: list,
        embedding_model: str,
        dimension: int,
        job_position: str,
        uploaded_at: datetime,
    ):
        document = {
            "resume_id": resume_id,
            "embedding": embedding,
            "embedding_model": embedding_model,
            "dimension": dimension,
            "job_position": job_position,
            "uploaded_at": uploaded_at,
            "created_at": datetime.utcnow(),
        }
        self.collection.insert_one(document)

    # Get Embedding
    def get_embedding(
        self,
        resume_id: str,
    ):
        return self.collection.find_one(
            {"resume_id": resume_id},
            {"_id": 0}

        )

    # Delete Embedding
    def delete_embedding(
        self,
        resume_id: str,
    ):
        self.collection.delete_one(
            {"resume_id": resume_id}
        )

    # MongoDB Atlas Vector Search
    def search_similar_embeddings(
        self,
        embedding: list,
        job_position: str,
        received_within: str,
    ):
        filter_query = {}
        if job_position.upper() != "ALL":
            filter_query["job_position"] = job_position

        if received_within != "ALL":
            now = datetime.utcnow()
            if received_within == "LAST_WEEK":
                filter_query["uploaded_at"] = {
                    "$gte": now - timedelta(days=7)
                }
            elif received_within == "LAST_MONTH":
                filter_query["uploaded_at"] = {
                    "$gte": now - timedelta(days=30)
                }
            elif received_within == "LAST_3_MONTHS":
                filter_query["uploaded_at"] = {
                    "$gte": now - timedelta(days=90)
                }
            elif received_within == "LAST_6_MONTHS":
                filter_query["uploaded_at"] = {
                    "$gte": now - timedelta(days=180)
                }
            elif received_within == "LAST_YEAR":
                filter_query["uploaded_at"] = {
                    "$gte": now - timedelta(days=365)
                }
        # Build Vector Search Stage

        vector_search = {
            "index": "resume_vector_index",
            "path": "embedding",
            "queryVector": embedding,
            "numCandidates": 10000,
            "limit": 10000,
        }

        # Apply filter only when required
        if filter_query:
            vector_search["filter"] = filter_query

        # Aggregation Pipeline
        pipeline = [
            {
                "$vectorSearch": vector_search
            },
            {
                "$project": {
                    "_id": 0,
                    "resume_id": 1,
                    "job_position": 1,
                    "uploaded_at": 1,
                    "embedding_score": {
                        "$meta": "vectorSearchScore"
                    },
                }
            },
        ]
        return list(
            self.collection.aggregate(
                pipeline
            )
        )

    # Count Embeddings
    def count_embeddings(
        self,
    ):
        return self.collection.count_documents(
            {}
        )
    # Delete All Embeddings
    def delete_all_embeddings(
        self,
    ):
        self.collection.delete_many(
            {}
        )

    # Update Embedding
    def update_embedding(
        self,
        resume_id: str,
        embedding: list,
    ):
        self.collection.update_one(
            {"resume_id": resume_id},
            {
                "$set": {
                    "embedding": embedding,
                    "updated_at": datetime.utcnow(),
                }
            }
        )

    # Embedding Exists
    def embedding_exists(
        self,
        resume_id: str,
    ) -> bool:
        return (
            self.collection.count_documents(
                {"resume_id": resume_id}
            )
            > 0
        )