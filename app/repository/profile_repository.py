from datetime import datetime, timedelta
from app.repository.base_repository import BaseRepository
from bson import ObjectId
from app.config.logging import logger

class ProfileRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.db["profiles"]

    def save_profile(
        self,
        resume,
        resume_path,
        file_hash,
        embedding,
        applicant_id,
    ):
        profile = resume.copy()

        profile["resume_path"] = resume_path
        profile["file_hash"] = file_hash

        profile["profile_embedding"] = embedding

        profile["created_at"] = datetime.utcnow()
        profile["updated_at"] = datetime.utcnow()
        profile["is_deleted"] = False
        profile["applicant_id"] = applicant_id

        result = self.collection.insert_one(profile)

        return str(result.inserted_id)
    
    def profile_exists(
        self,
        profile_id: str,
    ) -> bool:

        return (
            self.collection.count_documents(
                {
                    "_id": ObjectId(profile_id),
                    "is_deleted": False,
                }
            ) > 0
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
            },
            {
                "is_deleted": 0,
                "deleted_at": 0,
            },
        )

        if not profile:
            return None

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
            {"_id": ObjectId(profile_id)},
            {
                "$set": update_fields
            }
        )



    def resume_exists(
        self,
        file_hash: str,
    ) -> bool:

        return (
            self.collection.count_documents(
                {
                    "file_hash": file_hash,
                    "is_deleted": False,
                }
            )
            > 0
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
        job_id: str | None = None,
    ):

        filters = {

            "is_deleted": False,

        }

        if job_id:

            filters["job_id"] = job_id

        return list(

            self.collection.find(

                filters,

                {

                    "_id": 0,

                },

            )

        )

    # Soft Delete Profile
    def soft_delete_profile(
        self,
        profile_id: str,
    ):
        result = self.collection.update_one(
            {"_id": ObjectId(profile_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": datetime.utcnow(),
                }
            }
        )
        return result.modified_count > 0


    def search_similar_profiles(
            self,
            embedding,
            job_position_id,
            received_within,
            global_search_allowed,
        ):
            filter_query = {}
            if not global_search_allowed:
                filter_query["job_id"] = job_position_id
    
            if received_within != "ALL":
                now = datetime.utcnow()
                if received_within == "LAST_WEEK":
                    filter_query["applied_date"] = {
                        "$gte": now - timedelta(days=7)
                    }
                elif received_within == "LAST_MONTH":
                    filter_query["applied_date"] = {
                        "$gte": now - timedelta(days=30)
                    }
                elif received_within == "LAST_3_MONTHS":
                    filter_query["applied_date"] = {
                        "$gte": now - timedelta(days=90)
                    }
                elif received_within == "LAST_6_MONTHS":
                    filter_query["applied_date"] = {
                        "$gte": now - timedelta(days=180)
                    }
                elif received_within == "LAST_YEAR":
                    filter_query["applied_date"] = {
                        "$gte": now - timedelta(days=365)
                    }
            # Build Vector Search Stage
    
            vector_search = {
                "index": "resume_vector_index",
                "path": "profile_embedding",
                "queryVector": embedding,
                "numCandidates": 1000,
                "limit": 1000,
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

                        "profile_id": {
                            "$toString": "$_id"
                        },

                        "applicant_id": 1,

                        "job_id": 1,
                        "is_global_profile": 1, 

                        "candidate_name": 1,

                        "designation": 1,

                        "experience_years": 1,

                        "skills": 1,

                        "education": 1,

                        "projects": 1,

                        "certifications": 1,

                        "summary": 1,

                        "resume_text": 1,

                        "applied_date": 1,

                        "embedding_score": {

                            "$meta": "vectorSearchScore"

                        }

                    }
                },
            ]
            return list(
                self.collection.aggregate(
                    pipeline
                )
            )


    def get_applicant_id(
        self,
        profile_id: str,
    ):
        profile = self.collection.find_one(
            {
                "_id": ObjectId(profile_id),
                "is_deleted": False,
            },
            {
                "applicant_id": 1,
            },
        )

        if not profile:
            return None

        return profile.get("applicant_id")
    