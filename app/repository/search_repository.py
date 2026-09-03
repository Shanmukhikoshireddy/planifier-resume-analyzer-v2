from app.utils.datetime_utils import utc_now
from bson import ObjectId
from bson.errors import InvalidId
from app.utils.datetime_utils import utc_to_ist
from app.repository.base_repository import BaseRepository
from app.config.logging import logger


class SearchRepository(BaseRepository):

    def __init__(self):
        super().__init__()

        self.collection = self.db["searches"]
        self.search_results = self.db["search_results"]

    # =========================================================
    # ObjectId Safety
    # =========================================================

    @staticmethod
    def _valid_object_id(value):
        if not value:
            return None

        try:
            return ObjectId(str(value))
        except (InvalidId, TypeError):
            return None

    # =========================================================
    # Create Search
    # =========================================================

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
            "title": parsed_search.get(
                "title",
                "",
            ),

            "job_position_id": job_position_id,

            "parsed_search": parsed_search,

            "global_search_allowed": (
                global_search_allowed
            ),

            "original_prompt": original_prompt,

            "search_embedding": embedding,

            "received_within": received_within,

            "created_at": utc_now(),

            "updated_at": utc_now(),

            "status": "PROCESSING",

            "search_result_count": 0,

            "conversation": {
                "messages": [],

                "current_search": parsed_search,

                "latest_search_id": None,

                "context_summary": "",
            },
        }

        result = self.collection.insert_one(
            document
        )

        return str(result.inserted_id)

    # =========================================================
    # Get Latest Search Results
    #
    # IMPORTANT:
    #
    # latest_search_id stores the conversation_message_id
    # of the latest SEARCH / SEARCH_MODIFICATION response.
    #
    # Therefore we use that ID to retrieve the candidate
    # results belonging to that exact conversation turn.
    # =========================================================

    def get_latest_search_results(
        self,
        search_id: str,
    ):
        """
        Return the candidate set produced by the most recent
        SEARCH / SEARCH_MODIFICATION turn in this conversation.

        latest_search_id stores the conversation_message_id,
        NOT the Mongo search document id.
        """
        object_id = self._valid_object_id(search_id)

        if object_id is None:
            logger.warning(
                f"Invalid search_id supplied to get_latest_search_results: {search_id}"
            )
            return []

        latest_message_id = self.get_latest_search_id(
            search_id
        )

        # Primary path: use the explicit latest message id.
        if latest_message_id:
            results = self.get_search_results(
                search_id=search_id,
                conversation_message_id=latest_message_id,
            )

            if results:
                logger.info(
                    "Loaded %s previous candidates for search_id=%s "
                    "using latest conversation_message_id=%s",
                    len(results),
                    search_id,
                    latest_message_id,
                )
                return results

            logger.warning(
                "latest_search_id=%s has no results for search_id=%s. "
                "Trying result-history fallback.",
                latest_message_id,
                search_id,
            )

        # Recovery path: if the conversation field was not updated
        # correctly by an older request, recover the newest result
        # set directly from search_results.
        latest_result = self.search_results.find_one(
            {
                "search_id": search_id,
            },
            sort=[
                ("created_at", -1),
                ("rank", 1),
            ],
        )

        if not latest_result:
            logger.warning(
                "No previous search results found for search_id=%s",
                search_id,
            )
            return []

        recovered_message_id = latest_result.get(
            "conversation_message_id"
        )

        if not recovered_message_id:
            logger.warning(
                "Latest result has no conversation_message_id "
                "for search_id=%s",
                search_id,
            )
            return []

        results = self.get_search_results(
            search_id=search_id,
            conversation_message_id=recovered_message_id,
        )

        logger.info(
            "Recovered %s previous candidates for search_id=%s "
            "using conversation_message_id=%s",
            len(results),
            search_id,
            recovered_message_id,
        )

        return results

    # =========================================================
    # Update Search
    # =========================================================

    def update_search(
        self,
        search_id: str,
        update_fields: dict,
    ):

        update_fields = dict(
            update_fields
        )

        update_fields[
            "updated_at"
        ] = utc_now()

        self.collection.update_one(
            {
                "_id": ObjectId(search_id)
            },
            {
                "$set": update_fields
            }
        )

    # =========================================================
    # Get Search
    # =========================================================

    def get_search(
        self,
        search_id: str,
    ):

        object_id = self._valid_object_id(search_id)

        if object_id is None:
            logger.warning(
                "Invalid search_id supplied to get_search: %r",
                search_id,
            )
            return None

        document = self.collection.find_one(
            {
                "_id": object_id
            }
        )

        if not document:

            return None

        document["_id"] = str(
            document["_id"]
        )

        parsed_search = (
            document.get(
                "parsed_search",
                {}
            )
            or {}
        )

        # -----------------------------------------------------
        # IMPORTANT:
        # Return the complete parsed search context.
        #
        # Location was previously missing here.
        # -----------------------------------------------------

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
                {}
            ),

            "education": parsed_search.get(
                "education",
                ""
            ),

            "location": parsed_search.get(
                "location",
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

            "keywords": parsed_search.get(
                "keywords",
                []
            ),

            "status": document.get(
                "status"
            ),

            "created_at": document.get(
                "created_at"
            ),

            "original_prompt": document.get(
                "original_prompt",
                ""
            ),

            "received_within": document.get(
                "received_within",
                "ALL"
            ),

            "global_search_allowed": document.get(
                "global_search_allowed",
                False
            ),
        }

    # =========================================================
    # Shortlisted Profile IDs
    # =========================================================

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
            if result.get("profile_id")
        }

    # =========================================================
    # Get All Searches
    # =========================================================

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
                or job.get(
                    "parsed_search",
                    {}
                ).get(
                    "title"
                )
                or "New Conversation"
            )

            status = job.get(
                "status",
                "NEW"
            )

            if status == "COMPLETED":

                subtitle = (
                    f"{job.get('search_result_count', 0)} "
                    "Candidates"
                )

            elif status == "PROCESSING":

                subtitle = "Searching..."

            elif status == "NEW":

                subtitle = "New Conversation"

            else:

                subtitle = status.title()

            history.append(
                {
                    "search_id": str(
                        job["_id"]
                    ),

                    "title": prompt[:60],

                    "subtitle": subtitle,

                    "candidate_count": job.get(
                        "search_result_count",
                        0,
                    ),

                    "status": status,

                    "updated_at": utc_to_ist(
                        job.get("updated_at")
                    ),
                }
            )

        return history

    # =========================================================
    # Touch Search
    # =========================================================

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
                    "updated_at": utc_now(),
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

    # =========================================================
    # Get Chat
    # =========================================================

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

            content = message.get(
                "content"
            )

            if not isinstance(
                content,
                dict,
            ):

                continue

            if content.get("type") not in (
                "SEARCH",
                "SEARCH_MODIFICATION",
            ):

                continue

            conversation_message_id = (
                content.get(
                    "conversation_message_id"
                )
            )

            if not conversation_message_id:

                continue

            content["search_results"] = (
                self.get_search_results(
                    search_id=search_id,
                    conversation_message_id=(
                        conversation_message_id
                    ),
                )
            )

        return {

            "search_id": str(
                document["_id"]
            ),

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

    # =========================================================
    # Delete Search
    # =========================================================

    def delete_search(
        self,
        search_id: str,
    ):

        result = self.collection.update_one(
            {
                "_id": ObjectId(search_id),
                "is_deleted": {
                    "$ne": True
                },
            },
            {
                "$set": {
                    "is_deleted": True,
                    "updated_at": utc_now(),
                }
            },
        )

        if result.matched_count == 0:

            raise ValueError(
                "Search not found"
            )

        return {
            "search_id": search_id,
            "deleted": True,
        }

    # =========================================================
    # Count Searches
    # =========================================================

    def count_search(self):

        return self.collection.count_documents(
            {}
        )

    # =========================================================
    # Update Result Count
    # =========================================================

    def update_result_count(
        self,
        search_id: str,
        count: int,
    ):

        self.collection.update_one(
            {
                "_id": ObjectId(search_id)
            },
            {
                "$set": {
                    "search_result_count": count,
                    "updated_at": utc_now(),
                }
            }
        )

    # =========================================================
    # Update Status
    # =========================================================

    def update_status(
        self,
        search_id: str,
        status: str,
    ):

        self.collection.update_one(
            {
                "_id": ObjectId(search_id)
            },
            {
                "$set": {
                    "status": status,
                    "updated_at": utc_now(),
                }
            }
        )

    # =========================================================
    # Processing Jobs
    # =========================================================

    def get_processing_jobs(self):

        jobs = list(
            self.collection.find(
                {
                    "status": "PROCESSING"
                }
            )
        )

        for job in jobs:

            job["_id"] = str(
                job["_id"]
            )

        return jobs

    # =========================================================
    # Completed Jobs
    # =========================================================

    def get_completed_jobs(self):

        jobs = list(
            self.collection.find(
                {
                    "status": "COMPLETED"
                }
            ).sort(
                "created_at",
                -1,
            )
        )

        for job in jobs:

            job["_id"] = str(
                job["_id"]
            )

        return jobs

    # =========================================================
    # Latest Search
    # =========================================================

    def get_latest_search(self):

        job = self.collection.find_one(
            {
                "status": {
                    "$ne": "NEW"
                }
            },
            sort=[
                (
                    "updated_at",
                    -1
                )
            ]
        )

        if job:

            job["_id"] = str(
                job["_id"]
            )

        return job

    # =========================================================
    # Get Conversation
    # =========================================================

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

    # =========================================================
    # Update Conversation
    # =========================================================

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

                    "updated_at": utc_now(),

                }
            }
        )

    # =========================================================
    # Add Message
    # =========================================================

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

            "timestamp": utc_now(),

        }

        if (
            role == "assistant"
            and isinstance(
                content,
                dict,
            )
            and content.get("type") in (
                "SEARCH",
                "SEARCH_MODIFICATION",
            )
            and conversation_message_id
        ):

            message["content"][
                "conversation_message_id"
            ] = conversation_message_id

        self.collection.update_one(

            {
                "_id": ObjectId(search_id)
            },

            {
                "$push": {
                    "conversation.messages": message
                },

                "$set": {
                    "updated_at": utc_now()
                }
            }
        )

    # =========================================================
    # Update Current Search
    # =========================================================

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

                    "conversation.current_search": (
                        current_search
                    ),

                    "updated_at": utc_now(),

                }
            }
        )

    # =========================================================
    # Update Latest Search
    # =========================================================

    def update_latest_search(
        self,
        conversation_search_id: str,
        conversation_message_id: str,
    ):

        object_id = self._valid_object_id(
            conversation_search_id
        )

        if object_id is None:
            logger.warning(
                "Invalid conversation search_id supplied to "
                "update_latest_search: %r",
                conversation_search_id,
            )
            return

        if not conversation_message_id:
            logger.warning(
                "Empty conversation_message_id supplied to "
                "update_latest_search for search_id=%s",
                conversation_search_id,
            )
            return

        self.collection.update_one(

            {
                "_id": object_id
            },

            {
                "$set": {

                    "conversation.latest_search_id": (
                        conversation_message_id
                    ),

                    "updated_at": utc_now(),

                }
            }
        )

    # =========================================================
    # Create Empty Search
    # =========================================================

    def create_empty_search(self):

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

            "created_at": utc_now(),

            "updated_at": utc_now(),

        }

        result = self.collection.insert_one(
            document
        )

        return str(
            result.inserted_id
        )

    # =========================================================
    # Get Latest Search Message ID
    # =========================================================

    def get_latest_search_id(
        self,
        search_id: str,
    ):

        object_id = self._valid_object_id(search_id)

        if object_id is None:
            logger.warning(
                "Invalid search_id supplied to get_latest_search_id: %r",
                search_id,
            )
            return None

        document = self.collection.find_one(

            {
                "_id": object_id
            },

            {
                "conversation.latest_search_id": 1,
            }
        )

        if not document:
            return None

        return (
            document
            .get(
                "conversation",
                {}
            )
            .get(
                "latest_search_id"
            )
        )

    # =========================================================
    # Save Search Results
    # =========================================================

    def save_search_results(
        self,
        search_id: str,
        candidates: list,
        conversation_message_id: str,
    ):

        # Remove old results belonging to this
        # exact conversation message.

        self.search_results.delete_many(
            {
                "conversation_message_id": (
                    conversation_message_id
                ),
            }
        )

        documents = []

        for rank, candidate in enumerate(
            candidates,
            start=1,
        ):

            document = candidate.copy()

            document["search_id"] = search_id

            document["status"] = "PENDING"

            document[
                "conversation_message_id"
            ] = conversation_message_id

            document["rank"] = rank

            document["created_at"] = (
                utc_now()
            )

            documents.append(
                document
            )

        if documents:

            self.search_results.insert_many(
                documents
            )

        logger.info(
            "Saved %s search results for "
            "search_id=%s, conversation_message_id=%s",
            len(documents),
            search_id,
            conversation_message_id,
        )

    # =========================================================
    # Get Candidate
    # =========================================================

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

    # =========================================================
    # Get Reasoning
    # =========================================================

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

    # =========================================================
    # Save Reasoning
    # =========================================================

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

                    "updated_at": utc_now(),

                }
            },
        )

    # =========================================================
    # Get Candidate By Name
    # =========================================================

    def get_candidate_by_name(
        self,
        search_id: str,
        candidate_name: str,
    ):

        return self.search_results.find_one(

            {
                "search_id": search_id,

                "candidate_name": {
                    "$regex": (
                        f"^{candidate_name}$"
                    ),
                    "$options": "i",
                },
            }
        )

    # =========================================================
    # Get Results By Conversation Message
    # =========================================================

    def get_results_by_conversation_message(
        self,
        conversation_message_id: str,
        search_id: str = None,
    ):

        query = {
            "conversation_message_id": conversation_message_id,
        }

        if search_id:
            query["search_id"] = search_id

        results = list(
            self.search_results.find(
                query
            ).sort(
                "rank",
                1,
            )
        )

        for result in results:
            result["_id"] = str(
                result["_id"]
            )

        return results

    # =========================================================
    # Get Search Results
    # =========================================================

    def get_search_results(
        self,
        search_id: str,
        conversation_message_id: str,
    ):

        if not search_id or not conversation_message_id:
            return []

        results = list(
            self.search_results.find(
                {
                    "search_id": search_id,
                    "conversation_message_id": (
                        conversation_message_id
                    ),
                }
            ).sort(
                "rank",
                1,
            )
        )

        for result in results:
            result["_id"] = str(
                result["_id"]
            )

        return results

    # =========================================================
    # Shortlist Candidate
    # =========================================================

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

                    "updated_at": utc_now(),

                }
            },
        )

        return result.modified_count > 0

    # =========================================================
    # Reject Candidate
    # =========================================================

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

                    "updated_at": utc_now(),

                }
            },
        )

        return result.modified_count > 0

    # =========================================================
    # Undo Shortlist
    # =========================================================

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

                    "updated_at": utc_now(),

                }
            },
        )

        return result.modified_count > 0

    # =========================================================
    # Undo Reject
    # =========================================================

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

                    "updated_at": utc_now(),

                }
            },
        )

        return result.modified_count > 0

    # =========================================================
    # Get Rejected Candidates
    # =========================================================

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

            ).sort(
                "rank",
                1,
            )
        )

        for result in results:

            result["_id"] = str(
                result["_id"]
            )

        return results

    # =========================================================
    # Get Shortlisted Candidates
    # =========================================================

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

            ).sort(
                "rank",
                1,
            )
        )

        for result in results:

            result["_id"] = str(
                result["_id"]
            )

        return results