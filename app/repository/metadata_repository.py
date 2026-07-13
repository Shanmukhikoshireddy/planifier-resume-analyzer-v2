from datetime import datetime
from app.repository.base_repository import BaseRepository

class MetadataRepository(BaseRepository):
    """
    Stores processed MinIO objects.

    This collection is used by the scheduler to avoid
    processing the same object multiple times.
    """
    def __init__(self):
        super().__init__()
        self.collection = self.db["processed_resumes"]

    # Check Object Already Processed
    def is_processed(
        self,
        object_path: str,
    ) -> bool:
        document = self.collection.find_one(
            {
                "object_path": object_path,
                "status": "SUCCESS",
            }
        )
        return document is not None

    # Save Metadata
    def save_metadata(
        self,
        object_path: str,
        file_hash: str,
        status: str,
    ):
        now = datetime.utcnow()
        self.collection.update_one(
            {"object_path": object_path,},
            {
                "$set": {
                    "file_hash": file_hash,
                    "status": status,
                    "processed_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "object_path": object_path,
                    "created_at": now,
                }
            },
            upsert=True,
        )
    
    # Mark Processing
    def mark_processing(
        self,
        object_path: str,
    ):
        now = datetime.utcnow()
        self.collection.update_one(
            {
                "object_path": object_path,
            },
            {
                "$set": {
                    "status": "PROCESSING",
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "object_path": object_path,
                    "created_at": now,
                }
            },
            upsert=True,
        )

    # Update Status
    def update_status(
        self,
        object_path: str,
        status: str,
    ):

        self.collection.update_one(
            {
                "object_path": object_path,
            },
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    # Get Metadata
    def get_metadata(
        self,
        object_path: str,
    ):

        return self.collection.find_one(
            {
                "object_path": object_path,
            },
            {
                "_id": 0,
            },
        )


    # Get All Processed


    def get_all_processed(self):

        return list(
            self.collection.find(
                {},
                {
                    "_id": 0,
                },
            )
        )


    # Delete Metadata


    def delete_metadata(
        self,
        object_path: str,
    ):

        self.collection.delete_one(
            {
                "object_path": object_path,
            }
        )

    
    