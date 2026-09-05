from bson import ObjectId
from app.repository.base_repository import BaseRepository
from app.config.logging import logger


class JobPositionRepository(BaseRepository):

    use_planifier_db = True

    def __init__(self):
        super().__init__()
        self.collection = self.db["JOB_POSITIONS"]

    def get_job_position(self, job_id: str):
        logger.info(f"DB: {self.db.name}")
        logger.info(f"Collection: {self.collection.name}")

        job = self.collection.find_one(
            {"_id": ObjectId(job_id)}
        )

        logger.info(f"Job: {job}")

        return job

    def find_by_title(self, title: str):
        if not title:
            return None
        import re
        regex = re.escape(title.strip())
        return self.collection.find_one({
            "$or": [
                {"title": {"$regex": regex, "$options": "i"}},
                {"job_title": {"$regex": regex, "$options": "i"}},
                {"job_position": {"$regex": regex, "$options": "i"}},
                {"position": {"$regex": regex, "$options": "i"}},
            ]
        })