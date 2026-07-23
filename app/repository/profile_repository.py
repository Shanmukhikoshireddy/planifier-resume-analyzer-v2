from datetime import datetime
from app.repository.base_repository import BaseRepository
from bson import ObjectId

class ProfileRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.db["profiles"]

    # Save Profile
    def save_profile(
        self,
        resume: dict,
        resume_path: str,
        file_hash: str,
    ):
        """
        Save parsed resume profile.

        job_position is taken directly from the
        extracted resume JSON.
        """
        document = resume.copy()
        document["job_position"] = resume.get(
            "job_position",
            "Unknown",
        )
        document["resume_path"] = resume_path
        document["file_hash"] = file_hash
        document["is_deleted"] = False
        document["deleted_at"] = None
        document["uploaded_at"] = datetime.utcnow()
        document["created_at"] = datetime.utcnow()
        document["updated_at"] = datetime.utcnow()
        result = self.collection.insert_one(document)
        return str(result.inserted_id)

    # Duplicate Resume Check
    def resume_exists(
        self,
        file_hash: str,
    ) -> bool:
        return (
            self.collection.count_documents(
                {"file_hash": file_hash}
            )
            > 0
        )

    # Get Profile

    def get_profile(
        self,
        profile_id: str,
    ):
        profile = self.collection.find_one(
            {
                "_id": ObjectId(profile_id),
                "is_deleted": False,
            }
        )

        if not profile:
            return None

        # Expose profile_id to the application
        profile["profile_id"] = str(profile["_id"])
        del profile["_id"]

        return profile

    # Get All Profiles
    def get_all_profiles(
        self,
        filters: dict | None = None,
    ):
        if filters is None:
            filters = {}
        filters["is_deleted"] = False
        return list(
            self.collection.find(
                filters,
                { "_id": 0}
            )
        )

    # Update Profile
    def update_profile(
        self,
        profile_id: str,
        update_fields: dict,
    ):
        update_fields["updated_at"] = datetime.utcnow()
        self.collection.update_one(
            {"profile_id": profile_id},
            {"$set": update_fields}
        )

    # Delete Profile
    def delete_profile(
        self,
        profile_id: str,
    ):
        self.collection.delete_one(
            {"profile_id": profile_id}
        )

    # Count Profiles
    def count_profiles(
        self,
    ):
        return self.collection.count_documents(
            {}
        )

    # Filter Profiles
    def filter_profiles(
        self,
        job_position: str | None = None,
    ):
        filters = {"is_deleted": False}
        if job_position:
            filters["job_position"] = job_position
        return list(
            self.collection.find(
                filters,
                {"_id": 0}
            )
        )

    # Soft Delete Profile
    def soft_delete_profile(
        self,
        profile_id: str,
    ):
        result = self.collection.update_one(
            {"profile_id": profile_id},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": datetime.utcnow(),
                }
            }
        )
        return result.modified_count > 0