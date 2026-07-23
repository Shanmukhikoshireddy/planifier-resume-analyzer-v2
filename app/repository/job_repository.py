from datetime import datetime
from bson import ObjectId
from app.repository.base_repository import BaseRepository

class JobRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.db["jobs"]

    # Create Job
    def create_job(
        self,
        job: dict,
        original_prompt: str,
        embedding: list,
        job_position: str,
        received_within: str,
    ):
        document = {
            "title": job.get("title", ""),
            "job_position": job_position,
            "original_prompt": original_prompt,
            "prompt": job,
            "job_embedding": embedding,
            "received_within": received_within,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status": "PROCESSING",
            "cached": False,
            "search_result_count": 0,
            "conversation": {
                "messages": [],
                "current_job": job,
                "latest_search_id": None,
                "context_summary": "",
            },
        }
        result = self.collection.insert_one(document)
        return str(result.inserted_id)

    # Update Job
    def update_job(
        self,
        job_id: str,
        update_fields: dict,
    ):
        update_fields["updated_at"] = datetime.utcnow()
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_fields}
        )

    # Get Job
    def get_job(
        self,
        job_id: str,
    ):
        document = self.collection.find_one(
            {"_id": ObjectId(job_id)}
        )
        if not document:
            return None
        document["_id"] = str(document["_id"])

        # Flatten Parsed Job
        parsed_job = document.get(
            "prompt",
            {}
        )
        return {
            "job_id": document["_id"],
            "title": parsed_job.get(
                "title",
                ""
            ),
            "job_position": document.get(
                "job_position",
                ""
            ),
            "experience": parsed_job.get(
                "experience",
                ""
            ),

            "education": parsed_job.get(
                "education",
                ""
            ),

            "skills": parsed_job.get(
                "skills",
                []
            ),

            "certifications": parsed_job.get(
                "certifications",
                []
            ),

            "responsibilities": parsed_job.get(
                "responsibilities",
                []
            ),

            "qualifications": parsed_job.get(
                "qualifications",
                []
            ),

            "nice_to_have": parsed_job.get(
                "nice_to_have",
                []
            ),

            "status": document.get(
                "status"
            ),

            "created_at": document.get(
                "created_at"
            ),

        }
    # Get All Jobs (Sidebar)
    def get_all_jobs(self):

        jobs = list(
            self.collection.find(
                {
                    "status": {
                        "$ne": "NEW"
                    }
                },
                {
                    "prompt.title": 1,
                    "original_prompt": 1,
                    "updated_at": 1,
                    "status": 1,
                    "search_result_count": 1,
                },
            ).sort(
                "updated_at",
                -1,
            )
        )

        history = []

        for job in jobs:

            history.append({

                "job_id": str(job["_id"]),

                "title": job.get(
                    "prompt",
                    {},
                ).get(
                    "title",
                    ""
                ),

                "last_prompt": job.get(
                    "original_prompt",
                    "",
                ),

                "candidate_count": job.get(
                    "search_result_count",
                    0,
                ),

                "status": job.get(
                    "status",
                ),

                "updated_at": job.get(
                    "updated_at",
                ),

            })

        return history


    def get_chat(
        self,
        job_id: str,
    ):

        document = self.collection.find_one(
            {
                "_id": ObjectId(job_id)
            }
        )

        if document is None:
            return None

        return {

            "job_id": str(document["_id"]),

            "status": document.get(
                "status"
            ),

            "updated_at": document.get(
                "updated_at"
            ),

            "search_result_count": document.get(
                "search_result_count",
                0,
            ),

            "conversation": document.get(
                "conversation",
                {},
            ),
        }
    # Delete Job
    def delete_job(
        self,
        job_id: str,
    ):
        self.collection.delete_one(
            {"_id": ObjectId(job_id)}
        )

    # Count Jobs
    def count_jobs(self):
        return self.collection.count_documents({})

    # Find Similar Job (Cache)
    def find_similar_job(
        self,
        embedding: list,
        job_position: str,
        threshold: float = 0.95,
    ):
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "job_vector_index",
                    "path": "job_embedding",
                    "queryVector": embedding,
                    "numCandidates": 20,
                    "limit": 1,
                    "filter": {
                        "job_position": job_position
                    }
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "title": 1,
                    "job_position": 1,
                    "score": {
                        "$meta": "vectorSearchScore"
                    }
                }
            }
        ]
        jobs = list(
            self.collection.aggregate(
                pipeline
            )
        )
        if not jobs:
            return None
        if jobs[0]["score"] < threshold:
            return None
        return jobs[0]

    # Mark Cached
    def mark_as_cached(
        self,
        job_id: str,
    ):
        self.collection.update_one(
            { "_id": ObjectId(job_id)},
            {
                "$set": {
                    "cached": True,
                    "updated_at": datetime.utcnow(),
                }
            }
        )

    # Update Result Count
    def update_result_count(
        self,
        job_id: str,
        count: int,
    ):
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "search_result_count": count,
                    "updated_at": datetime.utcnow(),
                }
            }
        )

    # Update Status
    def update_status(
        self,
        job_id: str,
        status: str,
    ):
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow(),
                }
            }
        )

    # Get Processing Jobs
    def get_processing_jobs(self):
        jobs = list(
            self.collection.find(
                {"status": "PROCESSING"}
            )
        )
        for job in jobs:
            job["_id"] = str(job["_id"])
        return jobs

    # Get Completed Jobs
    def get_completed_jobs(self):
        jobs = list(
            self.collection.find(
                {"status": "COMPLETED"}
            ).sort(
                "created_at",
                -1,
            )
        )
        for job in jobs:
            job["_id"] = str(job["_id"])
        return jobs

    # Latest Job
    def get_latest_job(self):
        job = self.collection.find_one(
            sort=[
                ("created_at", -1)
            ]
        )
        if job:
            job["_id"] = str(job["_id"])
        return job
    


    ############################################################
    # Get Conversation
    ############################################################

    def get_conversation(
        self,
        job_id: str,
    ):

        document = self.collection.find_one(
            {
                "_id": ObjectId(job_id)
            }
        )

        if not document:

            return None

        return document.get(
            "conversation",
            {}
        )
    

    ############################################################
    # Update Conversation
    ############################################################

    def update_conversation(
        self,
        job_id: str,
        conversation: dict,
    ):

        self.collection.update_one(

            {
                "_id": ObjectId(job_id)
            },

            {
                "$set": {

                    "conversation": conversation,

                    "updated_at": datetime.utcnow(),

                }

            }

        )


    ############################################################
    # Add Message
    ############################################################

    def add_message(
        self,
        job_id: str,
        role: str,
        content,
    ):

        self.collection.update_one(

            {
                "_id": ObjectId(job_id)
            },

            {
                "$push": {

                    "conversation.messages": {

                        "role": role,

                        "content": content,

                        "timestamp": datetime.utcnow(),

                    }

                },

                "$set": {

                    "updated_at": datetime.utcnow(),

                }

            }

        )



    ############################################################
    # Update Current Job
    ############################################################

    def update_current_job(
        self,
        job_id: str,
        job: dict,
    ):

        self.collection.update_one(

            {
                "_id": ObjectId(job_id)
            },

            {
                "$set": {

                    "conversation.current_job": job,

                    "updated_at": datetime.utcnow(),

                }

            }

        )

    ############################################################
    # Update Latest Search
    ############################################################

    def update_latest_search(
        self,
        conversation_job_id: str,
        latest_search_job_id: str,
    ):

        self.collection.update_one(

            {
                "_id": ObjectId(conversation_job_id)
            },

            {
                "$set": {

                    "conversation.latest_search_id": latest_search_job_id,

                    "updated_at": datetime.utcnow(),

                }

            }

        )


    def create_empty_job(
        self,
    ):

        document = {

            "title": "",

            "job_position": "all",

            "original_prompt": "",

            "prompt": {},

            "job_embedding": [],

            "received_within": "ALL",

            "conversation": {

                "messages": [],

                "current_job": {},

                "latest_search_id": None,

                "context_summary": "",

            },

            "status": "NEW",

            "search_result_count": 0,

            "cached": False,

            "created_at": datetime.utcnow(),

            "updated_at": datetime.utcnow(),

        }

        result = self.collection.insert_one(document)

        return str(result.inserted_id)