from bson import ObjectId
from datetime import datetime
from app.repository.base_repository import BaseRepository
from app.config.logging import logger
from app.config.mongo import planifier_db
from app.utils.datetime_utils import utc_now
class ApplicantRepository:
    def __init__(self):

        self.db = planifier_db
        self.collection = self.db["applicants"]

    # Get all pending applicants
    def get_pending_applicants(self):
        applicants = list(
            self.collection.find(
                {
                    "$or": [
                        {"AI_SYNC_STATUS": {"$exists": False}},
                        {"AI_SYNC_STATUS": {"$in": ["PENDING", "FAILED"]}}
                    ]
                }
            )
        )

        logger.info(f"Fetched {len(applicants)} applicants")

        return applicants

    # Update AI sync status
    def update_ai_sync_status(
        self,
        applicant_id: str,
        status: str,
    ):
        self.collection.update_one(
            {
                "_id": ObjectId(applicant_id),
            },
            {
                "$set": {
                    "AI_SYNC_STATUS": status,
                }
            },
        )


    def get_applicant(
        self,
        applicant_id: str,
    ):
        applicant = self.collection.find_one(
            {
                "_id": ObjectId(applicant_id)
            }
        )

        if not applicant:
            return None

        applicant["applicant_id"] = str(applicant["_id"])
        del applicant["_id"]

        return applicant

    def get_all_applicants(self):
        applicants = list(self.collection.find())

        for applicant in applicants:
            applicant["applicant_id"] = str(applicant["_id"])
            del applicant["_id"]

        return applicants

    def update_status(
        self,
        applicant_id,
        status,
    ):
        self.collection.update_one(
            {
                "_id": ObjectId(applicant_id)
            },
            {
                "$set": {
                    "status": status,
                    "updatedAt": utc_now(),
                }
            }
        )
    def get_applicant_status_map(
        self,
        applicant_ids: list,
    ):

        object_ids = [
            ObjectId(applicant_id)
            for applicant_id in applicant_ids
        ]

        applicants = self.collection.find(
            {
                "_id": {
                    "$in": object_ids
                }
            },
            {
                "status": 1,
            },
        )

        status_map = {}

        for applicant in applicants:

            status_map[
                str(applicant["_id"])
            ] = applicant.get(
                "status",
                "DRAFT",
            )

        return status_map