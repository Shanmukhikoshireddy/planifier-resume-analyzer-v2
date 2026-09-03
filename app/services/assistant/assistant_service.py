from app.services.assistant.conversation_service import ConversationService
from app.services.assistant.context_builder import ContextBuilder
from app.services.assistant.intent_router import IntentRouter
from app.services.search.search_service import SearchService
from app.config.logging import logger
from fastapi import HTTPException
import re
from app.services.shared.openai_service import OpenAIService
import traceback

from app.services.orchestrator.prompt_parser_service import (
    PromptParserService,
)
from copy import deepcopy
from app.services.candidate.candidate_action_service import CandidateActionService
from app.repository.conversation_message_repository import ConversationMessageRepository
from app.repository.search_repository import SearchRepository
from app.repository.job_position_repository import JobPositionRepository
from app.utils.context_merger import ContextMerger

class AssistantService:

    def __init__(self):

        self.conversation_service = ConversationService()

        self.prompt_parser = PromptParserService()

        self.search_service = SearchService()

        self.context_builder = ContextBuilder()
        self.context_merger = ContextMerger()

        self.openai_service = OpenAIService()

        self.job_position_repository = JobPositionRepository()

        self.intent_router = IntentRouter()

        self.candidate_action_service = CandidateActionService()

        self.conversation_message_repository = (
            ConversationMessageRepository()
        )

        self.search_repository = SearchRepository()

    # =========================================================
    # MAIN ENTRY
    # =========================================================

    def process(
        self,
        request,
        page,
        page_size,
    ):

        logger.info("=" * 80)
        logger.info(
            f"Incoming request.search_id: {repr(request.search_id)}"
        )
        logger.info(
            f"Incoming request.job_position_id: "
            f"{repr(request.job_position_id)}"
        )
        logger.info(
            f"Prompt: {request.prompt}"
        )
        logger.info("=" * 80)

        # -----------------------------------------------------
        # Load / Create Conversation
        # -----------------------------------------------------

        if request.search_id:

            conversation = self.conversation_service.load(
                request.search_id
            )

            logger.info(
                f"Loaded conversation: "
                f"{conversation['search_id']}"
            )

        else:

            conversation = self.conversation_service.create()

            logger.info(
                f"Created conversation: "
                f"{conversation['search_id']}"
            )

        logger.info("=" * 80)
        logger.info(
            f"Conversation search_id: "
            f"{conversation['search_id']}"
        )
        logger.info("=" * 80)

        # -----------------------------------------------------
        # Detect Intent
        # -----------------------------------------------------

        intent_result = self.prompt_parser.detect_intent(
            request.prompt
        )

        intent = intent_result["intent"]

        logger.info(
            f"Detected Intent: {intent}"
        )

        # -----------------------------------------------------
        # IMPORTANT SEARCH/REFINEMENT RULE
        # -----------------------------------------------------
        # A search_id identifies the conversation, NOT one fixed
        # candidate query. Therefore a new role request inside an
        # existing conversation must start a fresh search.
        #
        # Examples that MUST be NEW SEARCHES:
        #   "I need Python developers"
        #   "Give me film directors"
        #   "Show me Java developers"
        #
        # Examples that MUST be MODIFICATIONS:
        #   "Only candidates with 5+ years"
        #   "Exclude Java"
        #   "Add React"
        #   "Change the location to Bangalore"
        #
        # The old implementation treated every SEARCH after the
        # first message as SEARCH_MODIFICATION. That caused a query
        # such as Python -> Film Director to reuse the previous
        # search context/candidates.
        # -----------------------------------------------------

        if intent == "SEARCH" and request.search_id:

            prompt = request.prompt.lower().strip()

            modification_patterns = [
                r"\badd\s+(?:the\s+)?(?:skill|skills|requirement|requirements)?",
                r"\binclude\s+(?:the\s+)?(?:skill|skills|requirement|requirements)?",
                r"\bexclude\s+",
                r"\bremove\s+",
                r"\bwithout\s+",
                r"\bdon['’]?\s*(?:show|include|consider)\s+",
                r"\bdo\s+not\s+(?:show|include|consider)\s+",
                r"\bonly\s+(?:candidates|profiles|people)\s+(?:with|having|who)",
                r"\bat\s+least\s+\d+\s+years?",
                r"\bminimum\s+\d+\s+years?",
                r"\bmaximum\s+\d+\s+years?",
                r"\bup\s+to\s+\d+\s+years?",
                r"\bchange\s+(?:the\s+)?(?:location|experience|education|skills?|title|role)",
                r"\bupdate\s+(?:the\s+)?(?:location|experience|education|skills?|title|role)",
                r"\bmodify\s+",
                r"\brefine\s+",
                r"\bnarrow\s+(?:the\s+)?search",
                r"\bfilter\s+(?:the\s+)?(?:results|candidates|profiles)",
                r"\bmake\s+the\s+search\s+",
                r"\b\d+\s+years?\s+(?:of\s+)?experience\b",
                r"\bwith\s+\d+\s+years?\s+(?:of\s+)?experience\b",
                r"\bhaving\s+\d+\s+years?\s+(?:of\s+)?experience\b",
                r"\bwho\s+(?:have|has)\s+\d+\s+years?\s+(?:of\s+)?experience\b",
                r"\b\d+\s*\+\s*years?\b",
            ]

            is_explicit_modification = any(
                re.search(pattern, prompt)
                for pattern in modification_patterns
            )

            if is_explicit_modification:
                intent = "SEARCH_MODIFICATION"

            else:
                # A role/profile request is an independent search even
                # when request.search_id belongs to an existing conversation.
                # Do NOT require the user to type "new search".
                intent = "SEARCH"

        logger.info(
            f"Final Intent: {intent}"
        )

        # -----------------------------------------------------
        # Default values
        # -----------------------------------------------------

        job_position = None

        # =====================================================
        # SEARCH / SEARCH MODIFICATION
        # =====================================================

        if intent in [
            "SEARCH",
            "SEARCH_MODIFICATION",
        ]:

            # =================================================
            # SEARCH MODIFICATION
            # =================================================

            if (
                intent == "SEARCH_MODIFICATION"
                and request.search_id
            ):

                # -------------------------------------------------
                # IMPORTANT:
                #
                # The search_id from the request/conversation is
                # the ID used for the existing search.
                #
                # DO NOT use conversation_message_id here.
                # DO NOT use response["search_id"] here.
                # -------------------------------------------------

                latest_search_id = conversation.get(
                    "latest_search_id"
                )

                # If latest_search_id was not stored for some
                # reason, use the conversation/search ID.
                if not latest_search_id:

                    latest_search_id = conversation.get(
                        "search_id"
                    )

                    logger.info(
                        "latest_search_id was empty. "
                        "Using conversation search_id: "
                        f"{latest_search_id}"
                    )

                logger.info("=" * 80)
                logger.info(
                    "SEARCH MODIFICATION"
                )
                logger.info(
                    f"Request search_id: "
                    f"{request.search_id}"
                )
                logger.info(
                    f"Conversation search_id: "
                    f"{conversation.get('search_id')}"
                )
                logger.info(
                    f"Latest search_id: "
                    f"{latest_search_id}"
                )
                logger.info("=" * 80)

                if not latest_search_id:

                    logger.info(
                        "No previous search found. "
                        "Starting a new search."
                    )

                    intent = "SEARCH"

                else:

                    # -------------------------------------------------
                    # Get existing search
                    # -------------------------------------------------

                    search = (
                        self.search_repository.get_search(
                            latest_search_id
                        )
                    )

                    logger.info(
                        f"Previous search result: {search}"
                    )

                    if search is None:

                        # -------------------------------------------------
                        # IMPORTANT FALLBACK:
                        #
                        # Sometimes latest_search_id can be stale.
                        # Since request.search_id is the conversation
                        # search ID, try that before failing.
                        # -------------------------------------------------

                        logger.warning(
                            "latest_search_id did not find "
                            "a search. Trying request.search_id."
                        )

                        fallback_search = (
                            self.search_repository.get_search(
                                request.search_id
                            )
                        )

                        if fallback_search is not None:

                            logger.info(
                                "Search found using "
                                "request.search_id."
                            )

                            search = fallback_search

                            latest_search_id = (
                                request.search_id
                            )

                            conversation[
                                "latest_search_id"
                            ] = latest_search_id

                            self.conversation_service.update_latest_search(
                                conversation,
                                latest_search_id,
                            )

                        else:

                            raise Exception(
                                "Previous search not found. "
                                f"latest_search_id="
                                f"{latest_search_id}, "
                                f"request.search_id="
                                f"{request.search_id}"
                            )

                    # -------------------------------------------------
                    # Get job position from previous search
                    # -------------------------------------------------

                    job_position_id = search.get(
                        "job_position_id"
                    )

                    if job_position_id:

                        job_position = (
                            self.job_position_repository
                            .get_job_position(
                                job_position_id
                            )
                        )

                        if job_position is None:

                            raise Exception(
                                "Job Position not found."
                            )

                    # -------------------------------------------------
                    # Build prompt using previous job details
                    # -------------------------------------------------

                    experience_modification = (
                        self.extract_experience_modification(
                            request.prompt
                        )
                    )

                    if experience_modification:

                        search_result = {
                            "job": {
                                "title": "",
                                "experience": experience_modification,
                                "education": "",
                                "location": "",
                                "required_skills": [],
                                "preferred_skills": [],
                                "excluded_skills": [],
                                "certifications": [],
                                "responsibilities": [],
                                "qualifications": [],
                                "nice_to_have": [],
                                "keywords": [],
                            }
                        }

                    else:

                        search_result = (
                            self.prompt_parser.parse_modification(
                                request.prompt
                            )
                        )
                        parsed_search = (
                            search_result.get("job")
                            or {}
                        )

                        validated_intent = (
                            self.determine_search_intent(
                                request=request,
                                conversation=conversation,
                                parsed_search=parsed_search,
                            )
                        )

                        logger.info(
                            f"Validated intent: {validated_intent}"
                        )

                        if validated_intent == "SEARCH":
                            final_intent = "SEARCH"

            # =================================================
            # NEW SEARCH
            # =================================================

            else:

                if request.global_search_allowed:

                    merged_prompt = request.prompt

                    if request.job_position_id:

                        job_position = (
                            self.job_position_repository
                            .get_job_position(
                                request.job_position_id
                            )
                        )

                    search_result = (
                        self.prompt_parser.parse_search(
                            merged_prompt
                        )
                    )

                else:

                    if not request.job_position_id:
                        raise HTTPException(
                            status_code=400,
                            detail="Please select a job position when Global Search is off.",
                        )

                    job_position = (
                        self.job_position_repository
                        .get_job_position(
                            request.job_position_id
                        )
                    )

                    logger.info(
                        f"Fetched Job Position: "
                        f"{job_position}"
                    )

                    if job_position is None:

                        raise Exception(
                            "Job Position not found."
                        )

                    context = (
                        self.conversation_service
                        .build_context(
                            conversation
                        )
                    )

                    search_result = (
                        self.prompt_parser.parse_search(
                            f"""
Current Search

{context}

User Request

{request.prompt}

Return the updated complete search.
"""
                        )
                    )

            # -------------------------------------------------
            # Parsed search
            # -------------------------------------------------

            parsed = {
                "intent": intent,
                "parsed_search": search_result["job"],
            }

        else:

            parsed = intent_result

        # =====================================================
        # SAVE USER MESSAGE
        # =====================================================

        conversation_message_id = (
            self.conversation_message_repository.create_message(
                search_id=conversation["search_id"],
                user_prompt=request.prompt,
                intent=parsed["intent"],
            )
        )

        conversation[
            "conversation_message_id"
        ] = conversation_message_id

        self.conversation_service.add_user_message(
            conversation,
            request.prompt,
        )

        # -----------------------------------------------------
        # Update search timestamp / prompt
        # -----------------------------------------------------

        self.search_repository.touch_search(
            conversation["search_id"],
            request.prompt,
        )

        # =====================================================
        # ROUTE INTENT
        # =====================================================

        try:

            return self.intent_router.route(
                assistant=self,
                intent=parsed["intent"],
                conversation=conversation,
                parsed=parsed,
                job_position=job_position,
                request=request,
                page=page,
                page_size=page_size,
            )

        except Exception:

            logger.exception(
                "Assistant routing failed."
            )

            raise

    # =========================================================
    # BUILD SEARCH CONTEXT
    # =========================================================

    def build_search_context(
        self,
        conversation,
        parsed_search,
        job_position,
        request,
        is_new_search,
    ):

        job_position_id = None

        if job_position:

            job_position_id = str(
                job_position["_id"]
            )

        elif request.job_position_id:

            job_position_id = request.job_position_id

        elif conversation.get(
            "search_id"
        ):

            search = (
                self.search_repository.get_search(
                    conversation["search_id"]
                )
            )

            if search:

                job_position_id = search.get(
                    "job_position_id"
                )

        return {

            # IMPORTANT:
            # Always use conversation search_id.
            "search_id": conversation[
                "search_id"
            ],

            "job_position_id": job_position_id,

            "job_description":
                job_position["jobDescription"]
                if job_position
                else None,

            "parsed_search": parsed_search,

            "original_prompt": request.prompt,

            "received_within":
                request.received_within,

            "global_search_allowed":
                request.global_search_allowed,

            "is_new_search": is_new_search,
        }

    # =========================================================
    # EXECUTE SEARCH
    # =========================================================

    def execute_search(
        self,
        conversation,
        merged_search,
        job_position,
        request,
        page,
        page_size,
        is_new_search,
        message_type,
    ):

        search_context = (
            self.build_search_context(
                conversation=conversation,
                parsed_search=merged_search,
                job_position=job_position,
                request=request,
                is_new_search=is_new_search,
            )
        )

        logger.info("=" * 80)
        logger.info(
            "Executing Search"
        )
        logger.info(
            f"Conversation search_id: "
            f"{conversation['search_id']}"
        )
        logger.info(
            f"Conversation message_id: "
            f"{conversation['conversation_message_id']}"
        )
        logger.info(
            f"is_new_search: "
            f"{is_new_search}"
        )
        logger.info("=" * 80)

        response = self.search_service.execute(
            search_context,
            page,
            page_size,
            conversation[
                "conversation_message_id"
            ],
        )

        logger.info("=" * 80)
        logger.info(
            f"Search response: {response}"
        )
        logger.info("=" * 80)

        self.conversation_message_repository.update_message(
            message_id=conversation[
                "conversation_message_id"
            ],
            assistant_message={
                "type": message_type,
                "total_candidates":
                    response[
                        "total_candidates"
                    ],
            },
        )

        # -----------------------------------------------------
        # IMPORTANT FIX
        #
        # DO NOT take search_id from response.
        #
        # The conversation/search ID is the stable ID for
        # this search conversation.
        # -----------------------------------------------------

        search_id = conversation[
            "search_id"
        ]

        # latest_search_id stores the conversation_message_id
        # of the most recent SEARCH / SEARCH_MODIFICATION result.
        latest_result_message_id = conversation[
            "conversation_message_id"
        ]

        conversation[
            "latest_search_id"
        ] = latest_result_message_id

        logger.info(
            f"Setting latest_search_id = "
            f"{latest_result_message_id}"
        )

        self.conversation_service.update_latest_search(
            conversation,
            latest_result_message_id,
        )

        # -----------------------------------------------------
        # Assistant message
        # -----------------------------------------------------

        self.conversation_service.add_assistant_message(
            conversation=conversation,
            message={
                "type": message_type,
                "results":
                    response[
                        "total_candidates"
                    ],
            },
            conversation_message_id=conversation[
                "conversation_message_id"
            ],
        )

        return response

    # =========================================================
    # NEW SEARCH
    # =========================================================

    def handle_search(
        self,
        conversation,
        parsed,
        job_position,
        request,
        page,
        page_size,
    ):

        conversation[
            "current_search"
        ] = parsed["parsed_search"]

        self.conversation_service.save(
            conversation["search_id"],
            conversation,
        )

        return self.execute_search(
            conversation=conversation,
            merged_search=parsed[
                "parsed_search"
            ],
            job_position=job_position,
            request=request,
            page=page,
            page_size=page_size,
            is_new_search=True,
            message_type="SEARCH",
        )

    def determine_search_intent(
        self,
        request,
        conversation,
        parsed_search,
    ):
        """
        Determines whether the current prompt is a new SEARCH
        or a modification of the existing search.

        Important:
        Empty fields in parsed_search mean the user did not mention
        that field. They do NOT mean that the user wants to remove
        the previous value.
        """

        current_search = (
            conversation.get("current_search")
            or {}
        )

        # --------------------------------------------------
        # No previous search
        # --------------------------------------------------

        if not current_search:
            return "SEARCH"

        # --------------------------------------------------
        # Different job position = completely new search
        # --------------------------------------------------

        current_job_position_id = str(
            current_search.get(
                "job_position_id",
                "",
            )
            or ""
        )

        request_job_position_id = str(
            getattr(
                request,
                "job_position_id",
                "",
            )
            or ""
        )

        if (
            request_job_position_id
            and current_job_position_id
            and request_job_position_id
            != current_job_position_id
        ):
            logger.info(
                "Different job_position_id detected. "
                "Using SEARCH."
            )

            return "SEARCH"

        # --------------------------------------------------
        # Detect explicit replacement language
        # --------------------------------------------------

        prompt = (
            getattr(
                request,
                "prompt",
                "",
            )
            or ""
        ).lower().strip()

        replacement_phrases = [
            "instead of",
            "replace",
            "replaced by",
            "change to",
            "switch to",
            "rather than",
        ]

        for phrase in replacement_phrases:

            if phrase in prompt:

                logger.info(
                    "Replacement language detected: %s. "
                    "Using SEARCH.",
                    phrase,
                )

                return "SEARCH"

        # --------------------------------------------------
        # Detect a new role/title
        # --------------------------------------------------

        new_title = (
            parsed_search.get("title")
            or ""
        )

        old_title = (
            current_search.get("title")
            or ""
        )

        if isinstance(new_title, str):
            new_title = new_title.strip()

        if isinstance(old_title, str):
            old_title = old_title.strip()

        if (
            new_title
            and old_title
            and new_title.lower()
            != old_title.lower()
        ):

            logger.info(
                "Different title detected: %s -> %s. "
                "Using SEARCH.",
                old_title,
                new_title,
            )

            return "SEARCH"

        # --------------------------------------------------
        # Otherwise treat explicitly provided constraints
        # as modifications.
        #
        # Empty fields are ignored.
        # --------------------------------------------------

        explicit_fields = []

        # --------------------------------------------------
        # Education
        #
        # Supports both:
        #
        # Old:
        # "B.Tech"
        #
        # New:
        # {
        #     "value": "B.Tech",
        #     "search_terms": [...]
        # }
        # --------------------------------------------------

        education = (
            parsed_search.get("education")
            or {}
        )

        if isinstance(education, dict):

            education_value = (
                education.get("value")
                or ""
            )

            education_terms = (
                education.get("search_terms")
                or []
            )

            if (
                education_value
                or education_terms
            ):
                explicit_fields.append(
                    "education"
                )

        elif education:

            # Backward compatibility
            explicit_fields.append(
                "education"
            )

        # --------------------------------------------------
        # Other simple fields
        # --------------------------------------------------

        for field in [
            "location",
            "certifications",
            "responsibilities",
            "qualifications",
            "nice_to_have",
            "keywords",
        ]:

            value = parsed_search.get(field)

            if value not in (
                None,
                "",
                [],
                {},
            ):

                explicit_fields.append(field)

        # --------------------------------------------------
        # Skills
        # --------------------------------------------------

        for field in [
            "required_skills",
            "preferred_skills",
            "excluded_skills",
        ]:

            value = parsed_search.get(field)

            if value:

                explicit_fields.append(field)

        # --------------------------------------------------
        # Experience
        # --------------------------------------------------

        experience = (
            parsed_search.get("experience")
            or {}
        )

        if (
            experience.get("min") is not None
            or experience.get("max") is not None
        ):

            explicit_fields.append(
                "experience"
            )

        # --------------------------------------------------
        # Explicit modification detected
        # --------------------------------------------------

        if explicit_fields:

            logger.info(
                "Explicit modification fields: %s",
                explicit_fields,
            )

            return "SEARCH_MODIFICATION"

        # --------------------------------------------------
        # Safe fallback
        # --------------------------------------------------

        return "SEARCH"

    # =========================================================
    # SEARCH MODIFICATION
    # =========================================================

    def modify_search(
        self,
        conversation,
        parsed,
        request,
        job_position,
        page,
        page_size,
    ):
        logger.info(
            f"Conversation search_id: "
            f"{conversation.get('search_id')}"
        )

        logger.info(
            f"Conversation latest_search_id: "
            f"{conversation.get('latest_search_id')}"
        )

        previous_result_message_id = None

        messages = conversation.get("messages", [])

        for message in reversed(messages):

            if not isinstance(message, dict):
                continue

            if message.get("role") != "assistant":
                continue

            content = message.get("content")

            if not isinstance(content, dict):
                continue

            if content.get("type") == "SEARCH":

                previous_result_message_id = (
                    content.get("conversation_message_id")
                )

                if previous_result_message_id:
                    break

        logger.info(
            f"Previous result message id: "
            f"{previous_result_message_id}"
        )

        logger.info(
            f"Captured previous_result_message_id: "
            f"{previous_result_message_id}"
        )

        logger.info("=" * 80)
        logger.info(
            "SEARCH MODIFICATION"
        )
        logger.info(
            f"Request search_id: "
            f"{request.search_id}"
        )
        logger.info(
            f"Conversation search_id: "
            f"{conversation.get('search_id')}"
        )
        logger.info(
            f"Latest search_id BEFORE modification: "
            f"{conversation.get('latest_search_id')}"
        )
        logger.info("=" * 80)

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # Always use the conversation/request search_id.
        # Do not use conversation_message_id.
        # -----------------------------------------------------

        search_id = conversation.get(
            "search_id"
        )

        if not search_id:

            search_id = request.search_id

        if not search_id:

            raise Exception(
                "Search ID is missing. "
                "Cannot modify previous search."
            )

        

        # -----------------------------------------------------
        # Verify previous search
        # -----------------------------------------------------

        previous_search = (
            self.search_repository.get_search(
                search_id
            )
        )

        logger.info(
            f"Previous search using search_id "
            f"{search_id}: {previous_search}"
        )

        if previous_search is None:

            raise Exception(
                "Previous search not found. "
                f"search_id={search_id}"
            )

        # -----------------------------------------------------
        # Merge previous search + new modification
        # -----------------------------------------------------

        previous_search_for_merge = deepcopy(
            previous_search
        )

        # Remove database/search metadata.
        # ContextMerger should only merge parsed search fields.
        previous_search_for_merge.pop(
            "search_id",
            None,
        )

        previous_search_for_merge.pop(
            "job_position_id",
            None,
        )

        previous_search_for_merge.pop(
            "status",
            None,
        )

        previous_search_for_merge.pop(
            "created_at",
            None,
        )

        previous_search_for_merge.pop(
            "original_prompt",
            None,
        )

        previous_search_for_merge.pop(
            "received_within",
            None,
        )

        previous_search_for_merge.pop(
            "global_search_allowed",
            None,
        )

        logger.info(
            "Previous search used for merge: %s",
            previous_search_for_merge,
        )

        logger.info(
            "Modification parsed search: %s",
            parsed["parsed_search"],
        )

        merged_search = self.context_merger.merge(
            previous_search_for_merge,
            parsed["parsed_search"],
        )

        logger.info(
            "Merged search: %s",
            merged_search,
        )

        conversation["current_search"] = merged_search

        self.conversation_service.save(
            conversation["search_id"],
            conversation,
        )

        logger.info(
            f"Merged search: {merged_search}"
        )

        # -----------------------------------------------------
        # Build search context
        # -----------------------------------------------------

        search_context = (
            self.build_search_context(
                conversation=conversation,
                parsed_search=merged_search,
                job_position=job_position,
                request=request,
                is_new_search=False,
            )
        )

        # -----------------------------------------------------
        # Refine previous search results
        # -----------------------------------------------------

        # -----------------------------------------------------
        # Experience-only modification
        # -----------------------------------------------------

        modification = parsed["parsed_search"]

        experience = modification.get("experience") or {}

        is_experience_only = (
            (
                experience.get("min") is not None
                or experience.get("max") is not None
            )
            and not modification.get("title")
            and not modification.get("location")
            and not modification.get("required_skills")
            and not modification.get("preferred_skills")
            and not modification.get("excluded_skills")
            and not modification.get("education")
            and not modification.get("certifications")
            and not modification.get("responsibilities")
            and not modification.get("qualifications")
            and not modification.get("nice_to_have")
            and not modification.get("keywords")
        )

        if is_experience_only:

            logger.info(
                "Experience-only modification. "
                "Filtering previous candidates directly."
            )

            previous_candidates = (
                self.search_service
                .search_repository
                .get_results_by_conversation_message(
                    previous_result_message_id,
                )
            )

            logger.info(
                f"Previous candidates before experience filter: "
                f"{len(previous_candidates)}"
            )

            candidates = (
                self.search_service
                .candidate_filter_service
                .filter_by_experience(
                    previous_candidates,
                    experience,
                )
            )

            logger.info(
                f"Candidates after experience filter: "
                f"{len(candidates)}"
            )

            total_candidates = len(candidates)

            start = (page - 1) * page_size
            end = start + page_size

            response = {
                "search_id": conversation["search_id"],
                "page": page,
                "page_size": page_size,
                "total_candidates": total_candidates,
                "total_pages": (
                    (total_candidates + page_size - 1)
                    // page_size
                    if total_candidates
                    else 0
                ),
                "results": candidates[start:end],
            }

        else:
            

            response = (
                self.search_service
                .refine_previous_results(
                    search_context=search_context,
                    page=page,
                    page_size=page_size,
                    conversation_message_id=
                        conversation[
                            "conversation_message_id"
                        ],
                    previous_result_message_id=(
                        previous_result_message_id
                    ),
                )
            )

        logger.info("=" * 80)
        logger.info(
            f"Refined search response: "
            f"{response}"
        )
        logger.info("=" * 80)

        # -----------------------------------------------------
        # Update conversation message
        # -----------------------------------------------------

        self.conversation_message_repository.update_message(
            message_id=conversation[
                "conversation_message_id"
            ],
            assistant_message={
                "type":
                    "SEARCH_MODIFICATION",
                "total_candidates":
                    response[
                        "total_candidates"
                    ],
            },
        )

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # Keep SAME search_id for every filter.
        #
        # Filter 1 -> same ID
        # Filter 2 -> same ID
        # Filter 3 -> same ID
        # Filter 4 -> same ID
        # -----------------------------------------------------

        # The current refinement has now produced the newest
        # candidate result set. Point latest_search_id to THIS
        # turn's conversation message so the next refinement
        # uses these results.
        latest_result_message_id = conversation[
            "conversation_message_id"
        ]

        conversation[
            "latest_search_id"
        ] = latest_result_message_id

        self.conversation_service.update_latest_search(
            conversation,
            latest_result_message_id,
        )

        # -----------------------------------------------------
        # Save updated current search
        # -----------------------------------------------------

        conversation[
            "current_search"
        ] = merged_search

        self.conversation_service.save(
            conversation["search_id"],
            conversation,
        )

        # -----------------------------------------------------
        # Assistant message
        # -----------------------------------------------------

        self.conversation_service.add_assistant_message(
            conversation=conversation,
            message={
                "type":
                    "SEARCH_MODIFICATION",
                "results":
                    response[
                        "total_candidates"
                    ],
            },
            conversation_message_id=
                conversation[
                    "conversation_message_id"
                ],
        )

        return response
    def extract_experience_modification(
        self,
        prompt: str,
    ):
        text = prompt.lower().strip()

        # --------------------------------------------------
        # More than N years
        # --------------------------------------------------

        match = re.search(
            r"(?:more than|over|above|greater than)\s+(\d+)\s+years?",
            text,
        )

        if match:
            years = int(match.group(1))

            return {
                "min": years,
                "max": None,
                "min_operator": ">",
                "max_operator": None,
            }

        # --------------------------------------------------
        # Minimum N years
        # --------------------------------------------------

        match = re.search(
            r"\b(?:min|minimum|at least)\s*(\d+)\s*years?",
            text,
        )

        if match:
            years = int(match.group(1))

            return {
                "min": years,
                "max": None,
                "min_operator": ">=",
                "max_operator": None,
            }

        # --------------------------------------------------
        # N+ years
        # --------------------------------------------------

        match = re.search(
            r"(\d+)\s*\+\s*years?",
            text,
        )

        if match:
            years = int(match.group(1))

            return {
                "min": years,
                "max": None,
                "min_operator": ">=",
                "max_operator": None,
            }

        # --------------------------------------------------
        # Only / exactly N years
        # --------------------------------------------------

        match = re.search(
            r"(?:only|exactly)\s+(\d+)\s+years?",
            text,
        )

        if match:
            years = int(match.group(1))

            return {
                "min": years,
                "max": years,
                "min_operator": ">=",
                "max_operator": "<=",
            }

        # --------------------------------------------------
        # Plain N years of experience
        # --------------------------------------------------

        match = re.search(
            r"\b(\d+)\s+years?\s+(?:of\s+)?experience\b",
            text,
        )

        if match:
            years = int(match.group(1))

            return {
                "min": years,
                "max": years,
                "min_operator": ">=",
                "max_operator": "<=",
            }

        return None
    # =========================================================
    # GENERAL QUESTIONS
    # =========================================================

    def answer_general(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        context = (
            self.context_builder.build()
        )

        conversation_context = (
            self.conversation_service
            .build_context(
                conversation
            )
        )

        messages = [

            {
                "role": "system",
                "content": context,
            },

            {
                "role": "system",
                "content": conversation_context,
            },

            {
                "role": "user",
                "content": request.prompt,
            },

        ]

        answer = (
            self.openai_service.generate(
                messages
            )
        )

        self.conversation_service.add_assistant_message(
            conversation,
            answer,
        )

        return {
            "search_id":
                conversation["search_id"],
            "type": "GENERAL",
            "answer": answer,
        }

    # =========================================================
    # SEARCH HISTORY
    # =========================================================

    def search_history(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        return {
            "type": "SEARCH_HISTORY",
            "messages":
                conversation.get(
                    "messages",
                    [],
                ),
        }

    # =========================================================
    # COMPARE CANDIDATES
    # =========================================================

    def compare_candidates(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        return {
            "type": "COMPARE_CANDIDATES",
            "message": "Not implemented yet.",
        }

    # =========================================================
    # CANDIDATE REASONING
    # =========================================================

    def candidate_reasoning(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        if not request.search_id:

            return {
                "success": False,
                "message":
                    "Please perform a search first.",
            }

        candidate = (
            self.search_service
            .search_repository
            .get_candidate_by_name(
                search_id=request.search_id,
                candidate_name=
                    parsed["candidate_name"],
            )
        )

        if candidate is None:

            return {
                "success": False,
                "message":
                    f"Candidate "
                    f"'{parsed['candidate_name']}' "
                    f"not found.",
            }

        response = (
            self.search_service
            .get_candidate_reasoning(
                search_id=request.search_id,
                profile_id=
                    candidate["profile_id"],
            )
        )

        self.conversation_service.add_assistant_message(
            conversation,
            response,
        )

        return response

    # =========================================================
    # RESET SEARCH
    # =========================================================

    def reset_search(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        return {
            "type": "RESET_SEARCH",
            "message":
                "Not implemented yet.",
        }

    # =========================================================
    # UNKNOWN INTENT
    # =========================================================

    def unknown_intent(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        return self.answer_general(
            conversation,
            parsed,
            request,
            page,
            page_size,
        )

    # =========================================================
    # SHORTLIST CANDIDATE
    # =========================================================

    def shortlist_candidate(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        response = (
            self.candidate_action_service.shortlist(
                search_id=request.search_id,
                candidate_name=
                    parsed["candidate_name"],
            )
        )

        self.conversation_service.add_assistant_message(
            conversation,
            response,
        )

        return response

    # =========================================================
    # REJECT CANDIDATE
    # =========================================================

    def reject_candidate(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        response = (
            self.candidate_action_service.reject(
                search_id=request.search_id,
                candidate_name=
                    parsed["candidate_name"],
            )
        )

        self.conversation_service.add_assistant_message(
            conversation,
            response,
        )

        return response

    # =========================================================
    # SHOW SHORTLISTED
    # =========================================================

    def show_shortlisted(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        candidates = (
            self.candidate_action_service.shortlisted(
                request.search_id,
            )
        )

        return {
            "search_id": request.search_id,
            "count": len(candidates),
            "results": candidates,
        }

    # =========================================================
    # SHOW REJECTED
    # =========================================================

    def show_rejected(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        candidates = (
            self.candidate_action_service.rejected(
                request.search_id,
            )
        )

        return {
            "search_id": request.search_id,
            "count": len(candidates),
            "results": candidates,
        }

    # =========================================================
    # UNDO SHORTLIST
    # =========================================================

    def undo_shortlist(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        logger.info(
            ">>> Assistant undo_shortlist"
        )

        response = (
            self.candidate_action_service
            .undo_shortlist(
                search_id=request.search_id,
                candidate_name=
                    parsed["candidate_name"],
            )
        )

        self.conversation_service.add_assistant_message(
            conversation,
            response,
        )

        logger.info(
            f">>> Response: {response}"
        )

        return response

    # =========================================================
    # UNDO REJECT
    # =========================================================

    def undo_reject(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        response = (
            self.candidate_action_service
            .undo_reject(
                search_id=request.search_id,
                candidate_name=
                    parsed["candidate_name"],
            )
        )

        self.conversation_service.add_assistant_message(
            conversation,
            response,
        )

        return response

    # =========================================================
    # CONVERSATION HISTORY
    # =========================================================

    def get_conversation_history(
        self,
        search_id: str,
    ):

        messages = (
            self.conversation_message_repository
            .get_messages(
                search_id,
            )
        )

        history = []

        for message in messages:

            candidates = (
                self.search_repository
                .get_results_by_conversation_message(
                    message["_id"],
                )
            )

            history.append(
                {
                    "conversation_message_id":
                        message["_id"],
                    "user_prompt":
                        message["user_prompt"],
                    "intent":
                        message["intent"],
                    "assistant_message":
                        message["assistant_message"],
                    "candidates":
                        candidates,
                }
            )

        return {
            "search_id": search_id,
            "history": history,
        }
