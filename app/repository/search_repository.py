from datetime import datetime
from bson import ObjectId
from app.repository.base_repository import BaseRepository
from app.config.logging import logger
class SearchRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self.collection = self.db["searches"]
        self.search_results = self.db["search_results"]

    # Create Job
    def create_search(
        self,
        parsed_search: dict,
        original_prompt: str,
        embedding: list,
        job_position_id: str,
        received_within: str,
        global_search_allowed: bool,
    ):
        document = {
            "title": parsed_search.get("title", ""),

            "job_position_id": job_position_id,

            "parsed_search": parsed_search,
            
            "global_search_allowed": global_search_allowed,
            "original_prompt": original_prompt,
            "search_embedding": embedding,
            "received_within": received_within,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status": "PROCESSING",
            "search_result_count": 0,
            "conversation": {
                "messages": [],
                "current_search": parsed_search,
                "latest_search_id": None,
                "context_summary": "",
            },
        }
        result = self.collection.insert_one(document)
        return str(result.inserted_id)

    def get_latest_search_results(
        self,
        search_id: str,
    ):

        latest_search_id = self.get_latest_search_id(
            search_id
        )

        if not latest_search_id:
            return []

        return self.get_results_by_conversation_message(
            latest_search_id
        )

    # Update Job
    def update_search(
        self,
        search_id: str,
        update_fields: dict,
    ):
        update_fields["updated_at"] = datetime.utcnow()
        self.collection.update_one(
            {"_id": ObjectId(search_id)},
            {"$set": update_fields}
        )

    # Get Job
    def get_search(
        self,
        search_id: str,
    ):
        document = self.collection.find_one(
            {"_id": ObjectId(search_id)}
        )
        if not document:
            return None
        document["_id"] = str(document["_id"])

        # Flatten Parsed Job
        parsed_search = document.get(
            "parsed_search",
            {}
        )
        return {
            "search_id": document["_id"],
            "title": parsed_search.get(
                "title",
                ""
            ),
            "job_position_id": document.get(
                "job_position_id",
                ""
            ),
            "experience": parsed_search.get(
                "experience",
                ""
            ),

            "education": parsed_search.get(
                "education",
                ""
            ),

            "required_skills": parsed_search.get(
                "required_skills",
                []
            ),

            "preferred_skills": parsed_search.get(
                "preferred_skills",
                []
            ),

            "excluded_skills": parsed_search.get(
                "excluded_skills",
                []
            ),

            "certifications": parsed_search.get(
                "certifications",
                []
            ),

            "responsibilities": parsed_search.get(
                "responsibilities",
                []
            ),

            "qualifications": parsed_search.get(
                "qualifications",
                []
            ),

            "nice_to_have": parsed_search.get(
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
    def get_shortlisted_profile_ids(
        self,
        search_id: str,
    ):
        results = self.search_results.find(
            {
                "search_id": search_id,
                "status": "SHORTLISTED",
            },
            {
                "profile_id": 1,
            },
        )

        return {
            result["profile_id"]
            for result in results
        }
    # Get All Jobs (Sidebar)
    def get_all_search(self):

        jobs = list(
            self.collection.find(
                {
            "is_deleted": {
                "$ne": True
            }
                },
                {
                    "parsed_search.title": 1,
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

            prompt = (
                job.get("original_prompt")
                or job.get("parsed_search", {}).get("title")
                or "New Conversation"
            )

            status = job.get("status", "NEW")

            if status == "COMPLETED":
                subtitle = f"{job.get('search_result_count',0)} Candidates"
            elif status == "PROCESSING":
                subtitle = "Searching..."
            elif status == "NEW":
                subtitle = "New Conversation"
            else:
                subtitle = status.title()

            history.append(
                {
                    "search_id": str(job["_id"]),
                    "title": prompt[:60],
                    "subtitle": subtitle,
                    "candidate_count": job.get(
                        "search_result_count",
                        0,
                    ),
                    "status": status,
                    "updated_at": job.get("updated_at"),
                }
            )

        return history

    def touch_search(
        self,
        search_id,
        prompt,
    ):

        self.collection.update_one(
            {
                "_id": ObjectId(search_id),
            },
            {
                "$set": {
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {},
            },
        )

        self.collection.update_one(
            {
                "_id": ObjectId(search_id),
                "original_prompt": "",
            },
            {
                "$set": {
                    "original_prompt": prompt,
                }
            },
        )
    def get_chat(
        self,
        search_id: str,
    ):

        document = self.collection.find_one(
            {
                "_id": ObjectId(search_id)
            }
        )

        if document is None:
            return None

        conversation = document.get(
            "conversation",
            {},
        )

        messages = conversation.get(
            "messages",
            [],
        )

        for message in messages:

            if message.get("role") != "assistant":
                continue

            content = message.get("content")

            if not isinstance(content, dict):
                continue

            if content.get("type") not in (
                "SEARCH",
                "SEARCH_MODIFICATION",
            ):
                continue

            conversation_message_id = content.get(
                "conversation_message_id"
            )

            if not conversation_message_id:
                continue

            content["search_results"] = self.get_search_results(
                search_id=search_id,
                conversation_message_id=conversation_message_id,
            )

        return {

            "search_id": str(document["_id"]),

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

            "conversation": conversation,

        }

    def delete_search(self, search_id: str):

        result = self.collection.update_one(
            {
                "_id": ObjectId(search_id),
                "is_deleted": {"$ne": True},
            },
            {
                "$set": {
                    "is_deleted": True,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        if result.matched_count == 0:
            raise ValueError("Search not found")

        return {
            "search_id": search_id,
            "deleted": True,
        }
    # Delete Job
    # def delete_search(
    #     self,
    #     search_id: str,
    # ):
    #     self.collection.delete_one(
    #         {"_id": ObjectId(search_id)}
    #     )

    # Count Jobs
    def count_search(self):
        return self.collection.count_documents({})

    
    # Update Result Count
    def update_result_count(
        self,
        search_id: str,
        count: int,
    ):
        self.collection.update_one(
            {"_id": ObjectId(search_id)},
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
        search_id: str,
        status: str,
    ):
        self.collection.update_one(
            {"_id": ObjectId(search_id)},
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
    def get_latest_search(self):

        job = self.collection.find_one(
            {
                "status": {
                    "$ne": "NEW"
                }
            },
            sort=[
                ("updated_at", -1)
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
        search_id: str,
    ):

        document = self.collection.find_one(
            {
                "_id": ObjectId(search_id)
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
        search_id: str,
        conversation: dict,
    ):

        self.collection.update_one(

            {
                "_id": ObjectId(search_id)
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
        search_id: str,
        role: str,
        content,
        conversation_message_id: str = None,
    ):
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
        }

        if (
            role == "assistant"
            and isinstance(content, dict)
            and content.get("type") in (
                "SEARCH",
                "SEARCH_MODIFICATION",
            )
            and conversation_message_id
        ):
            message["content"]["conversation_message_id"] = (
                conversation_message_id
            )

        self.collection.update_one(
            {
                "_id": ObjectId(search_id)
            },
            {
                "$push": {
                    "conversation.messages": message
                },
                "$set": {
                    "updated_at": datetime.utcnow()
                }
            }
        )



    ############################################################
    # Update Current Job
    ############################################################

    def update_current_search(
        self,
        search_id: str,
        current_search: dict,
    ):

        self.collection.update_one(

            {
                "_id": ObjectId(search_id)
            },

            {
                "$set": {

                    "conversation.current_search": current_search,

                    "updated_at": datetime.utcnow(),

                }

            }

        )

    ############################################################
    # Update Latest Search
    ############################################################

    def update_latest_search(
        self,
        conversation_search_id: str,
        conversation_message_id: str,
    ):

        self.collection.update_one(
            {
                "_id": ObjectId(conversation_search_id)
            },
            {
                "$set": {
                    "conversation.latest_search_id": conversation_message_id,
                    "updated_at": datetime.utcnow(),
                }
            }
        )


    def create_empty_search(
        self,
    ):

        document = {

            "title": "",

            "job_position_id": "",

            "parsed_search": {},

            "global_search_allowed": False,

            "original_prompt": "",

            "search_embedding": [],

            "received_within": "ALL",

            "conversation": {

                "messages": [],

                "current_search": {},

                "latest_search_id": None,

                "context_summary": "",

            },

            "status": "NEW",

            "search_result_count": 0,

            "created_at": datetime.utcnow(),

            "updated_at": datetime.utcnow(),

        }

        result = self.collection.insert_one(document)

        return str(result.inserted_id)
    

    def get_latest_search_id(
        self,
        search_id: str,
    ):

        document = self.collection.find_one(
            {
                "_id": ObjectId(search_id)
            },
            {
                "conversation.latest_search_id": 1,
            }
        )

        if not document:
            return None

        return (
            document.get("conversation", {})
            .get("latest_search_id")
        )


    ############################################################
    # Save Search Results
    ############################################################

    def save_search_results(
        self,
        search_id: str,
        candidates: list,
        conversation_message_id: str,
    ):

        # Remove previous results for this conversation message
        self.search_results.delete_many(
            {
                "conversation_message_id": conversation_message_id,
            }
        )

        documents = []

        for rank, candidate in enumerate(candidates, start=1):

            document = candidate.copy()

            document["search_id"] = search_id
            document["status"] = "PENDING"
            document["conversation_message_id"] = conversation_message_id
            document["rank"] = rank
            document["created_at"] = datetime.utcnow()

            documents.append(document)

        if documents:
            self.search_results.insert_many(documents)


    ############################################################
    # Get Candidate
    ############################################################

    def get_candidate(
        self,
        search_id: str,
        profile_id: str,
    ):

        return self.search_results.find_one(
            {
                "search_id": search_id,
                "profile_id": profile_id,
            }
        )


    ############################################################
    # Get Reasoning
    ############################################################

    def get_reasoning(
        self,
        search_id: str,
        profile_id: str,
    ):

        return self.search_results.find_one(
            {
                "search_id": search_id,
                "profile_id": profile_id,
            },
            {
                "reasoning": 1,
                "reasoning_generated": 1,
            },
        )


    ############################################################
    # Save Reasoning
    ############################################################

    def save_reasoning(
        self,
        search_id: str,
        profile_id: str,
        reasoning: str,
    ):

        self.search_results.update_one(
            {
                "search_id": search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "reasoning": reasoning,
                    "reasoning_generated": True,
                    "updated_at": datetime.utcnow(),
                }
            },
        )


    ############################################################
    # Get Candidate By Name
    ############################################################

    def get_candidate_by_name(
        self,
        search_id: str,
        candidate_name: str,
    ):

        return self.search_results.find_one(
            {
                "search_id": search_id,
                "candidate_name": {
                    "$regex": f"^{candidate_name}$",
                    "$options": "i",
                },
            }
        )


    ############################################################
    # Get Results By Conversation Message
    ############################################################

    def get_results_by_conversation_message(
        self,
        conversation_message_id: str,
    ):

        results = list(
            self.search_results.find(
                {
                    "conversation_message_id": conversation_message_id,
                }
            ).sort("rank", 1)
        )

        for result in results:
            result["_id"] = str(result["_id"])

        return results

    ############################################################
    # Get Search Results
    ############################################################

    def get_search_results(
        self,
        search_id: str,
        conversation_message_id: str,
    ):

        results = list(
            self.search_results.find(
                {
                    "search_id": search_id,
                    "conversation_message_id": conversation_message_id,
                }
            ).sort("rank", 1)
        )

        for result in results:
            result["_id"] = str(result["_id"])

        return results


    def shortlist_candidate(
        self,
        search_id: str,
        profile_id: str,
    ):
        result = self.search_results.update_one(
            {
                "search_id": search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "status": "SHORTLISTED",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        return result.modified_count > 0


    def reject_candidate(
        self,
        search_id: str,
        profile_id: str,
    ):
        result = self.search_results.update_one(
            {
                "search_id": search_id,
                "profile_id": profile_id,
            },
            {
                "$set": {
                    "status": "REJECTED",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        return result.modified_count > 0


    def undo_shortlist(
        self,
        search_id: str,
        profile_id: str,
    ):
        result = self.search_results.update_one(
            {
                "search_id": search_id,
                "profile_id": profile_id,
                "status": "SHORTLISTED",
            },
            {
                "$set": {
                    "status": "PENDING",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        return result.modified_count > 0


    def undo_reject(
        self,
        search_id: str,
        profile_id: str,
    ):
        result = self.search_results.update_one(
            {
                "search_id": search_id,
                "profile_id": profile_id,
                "status": "REJECTED",
            },
            {
                "$set": {
                    "status": "PENDING",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        return result.modified_count > 0



    def get_rejected_candidates(
        self,
        search_id: str,
    ):
        results = list(
            self.search_results.find(
                {
                    "search_id": search_id,
                    "status": "REJECTED",
                }
            ).sort("rank", 1)
        )

        for result in results:
            result["_id"] = str(result["_id"])

        return results

    def get_shortlisted_candidates(
            self,
            search_id: str,
        ):
            results = list(
                self.search_results.find(
                    {
                        "search_id": search_id,
                        "status": "SHORTLISTED",
                    }
                ).sort("rank", 1)
            )
    
            for result in results:
                result["_id"] = str(result["_id"])
    
            return results