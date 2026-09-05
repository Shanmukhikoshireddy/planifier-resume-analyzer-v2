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
            prompt_clean = re.sub(r"[.,?!:;]+$", "", prompt).strip()

            new_search_patterns = [
                r"\bnew\s+search\b",
                r"\bfresh\s+search\b",
                r"\bstart\s+(?:a\s+)?new\s+search\b",
                r"\bstart\s+over\b",
                r"\banother\s+search\b",
                r"\bclear\s+search\b",
                r"\breset\s+search\b",
                r"^\s*reset\s*$",
                r"\breset\s+all\b",
            ]

            is_explicit_new_search = any(
                re.search(pattern, prompt)
                for pattern in new_search_patterns
            )

            has_active_search = bool(
                conversation.get("current_search")
            ) or bool(
                conversation.get("latest_search_id")
            )

            show_candidates_patterns = [
                r"^(?:show|give|display|list|view|get|see)\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?candidates?(?:\s+list)?$",
                r"^i\s+want\s+(?:all\s+)?(?:the\s+)?candidates?(?:\s+list)?$",
                r"^(?:all\s+)?candidates?(?:\s+list)?$",
                r"^show\s+current\s+candidates?$",
                r"^(?:what|which)\s+(?:are\s+the\s+)?candidates?(?:\s+list)?$",
            ]

            if re.search(r"\b(?:show|get|give|want|list|view|see)?\s*(?:all\s+)?(?:the\s+)?(?:candidates?\s+)?(?:who\s+are\s+)?shortlisted\b", prompt_clean):
                intent = "SHOW_SHORTLISTED"
            elif re.search(r"\b(?:show|get|give|want|list|view|see)?\s*(?:all\s+)?(?:the\s+)?(?:candidates?\s+)?(?:who\s+are\s+)?rejected\b", prompt_clean):
                intent = "SHOW_REJECTED"
            elif has_active_search and any(re.search(pattern, prompt_clean) for pattern in show_candidates_patterns):
                intent = "SHOW_CANDIDATES"
            elif not is_explicit_new_search and has_active_search:
                intent = "SEARCH_MODIFICATION"
            else:
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

                    search_id = (
                        conversation.get("search_id")
                        or request.search_id
                    )

                    search = (
                        self.search_repository.get_search(
                            search_id
                        )
                    )

                    if search is None and latest_search_id:
                        search = (
                            self.search_repository.get_search(
                                latest_search_id
                            )
                        )

                    logger.info(
                        f"Previous search result: {search}"
                    )

                    if search is None:
                        logger.warning(
                            "Previous search not found for search_id=%s. "
                            "Starting a new search.",
                            search_id,
                        )
                        intent = "SEARCH"

                    if intent == "SEARCH_MODIFICATION":

                        # -------------------------------------------------
                        # Get job position from previous search
                        # -------------------------------------------------

                        job_position_id = (
                            search.get("job_position_id")
                            if search
                            else None
                        )

                        if job_position_id:

                            job_position = (
                                self.job_position_repository
                                .get_job_position(
                                    job_position_id
                                )
                            )

                        # -------------------------------------------------
                        # Build prompt using previous job details
                        # -------------------------------------------------

                        experience_modification = (
                            self.extract_experience_modification(
                                request.prompt
                            )
                        )

                        location_modification = (
                            self.extract_location_modification(
                                request.prompt
                            )
                        )

                        role_modification = (
                            self.extract_role_modification(
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

                        elif location_modification:

                            search_result = {
                                "job": {
                                    "title": "",
                                    "experience": {
                                        "min": None,
                                        "max": None,
                                        "min_operator": None,
                                        "max_operator": None,
                                    },
                                    "education": "",
                                    "location": location_modification,
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

                        elif role_modification:

                            search_result = {
                                "job": {
                                    "title": role_modification,
                                    "experience": {
                                        "min": None,
                                        "max": None,
                                        "min_operator": None,
                                        "max_operator": None,
                                    },
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
                                intent = "SEARCH"
                                search_result = (
                                    self.prompt_parser.parse_search(
                                        request.prompt
                                    )
                                )
                                if request.job_position_id and not job_position:
                                    job_position = (
                                        self.job_position_repository
                                        .get_job_position(
                                            request.job_position_id
                                        )
                                    )
                    else:

                        search_result = (
                            self.prompt_parser.parse_search(
                                request.prompt
                            )
                        )

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
                "parsed_search": search_result.get("job") or {},
            }

        else:

            parsed = dict(intent_result) if isinstance(intent_result, dict) else {}
            parsed["intent"] = intent

        # =====================================================
        # SAVE USER MESSAGE
        # =====================================================

        conversation_message_id = (
            self.conversation_message_repository.create_message(
                search_id=conversation["search_id"],
                user_prompt=request.prompt,
                intent=intent,
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
                intent=intent,
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
        parsed_search = (
            parsed.get("parsed_search")
            or conversation.get("current_search")
            or {}
        )

        conversation[
            "current_search"
        ] = parsed_search

        self.conversation_service.save(
            conversation["search_id"],
            conversation,
        )

        return self.execute_search(
            conversation=conversation,
            merged_search=parsed_search,
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

        new_search_phrases = [
            "new search",
            "fresh search",
            "start over",
            "another search",
            "clear search",
            "start a new search",
            "reset search",
            "reset all",
        ]

        if prompt == "reset" or any(phrase in prompt for phrase in new_search_phrases):

            logger.info(
                "New search / reset phrase detected in prompt: %s. "
                "Using SEARCH.",
                prompt,
            )

            return "SEARCH"

        # --------------------------------------------------
        # Location reclassification check
        # --------------------------------------------------
        new_title = (
            parsed_search.get("title")
            or ""
        )
        if isinstance(new_title, str):
            clean_new = new_title.strip()
            extracted_loc = self.extract_location_modification(clean_new)
            if extracted_loc:
                logger.info(
                    "Title '%s' reclassified as location: %s",
                    clean_new,
                    extracted_loc,
                )
                if not parsed_search.get("location"):
                    parsed_search["location"] = extracted_loc
                parsed_search["title"] = ""

        # --------------------------------------------------
        # Continuation turns in an active search conversation
        # are SEARCH_MODIFICATION (users have a dedicated reset
        # option/button when they want to start a new search).
        # --------------------------------------------------
        logger.info(
            "Continuation prompt in active search (%s). "
            "Using SEARCH_MODIFICATION.",
            conversation.get("search_id"),
        )
        return "SEARCH_MODIFICATION"

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

        # 1. First check if conversation.latest_search_id points to a message with results
        latest_search_id = conversation.get("latest_search_id")
        if latest_search_id:
            results_check = (
                self.search_repository
                .get_results_by_conversation_message(
                    latest_search_id
                )
            )
            if results_check:
                previous_result_message_id = latest_search_id

        # 2. If not found via latest_search_id, search backwards through messages
        if not previous_result_message_id:
            messages = conversation.get("messages", [])

            for message in reversed(messages):

                if not isinstance(message, dict):
                    continue

                if message.get("role") != "assistant":
                    continue

                content = message.get("content")

                if not isinstance(content, dict):
                    continue

                if content.get("type") in [
                    "SEARCH",
                    "SEARCH_MODIFICATION",
                ]:

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
            current_search = conversation.get("current_search")
            if current_search:
                logger.warning(
                    "Search document not found in database for search_id=%s. "
                    "Using conversation['current_search'] fallback.",
                    search_id,
                )
                previous_search = deepcopy(current_search)
                previous_search["search_id"] = search_id
            else:
                raise Exception(
                    "Previous search not found. "
                    f"search_id={search_id}"
                )

        # -----------------------------------------------------
        # Merge previous search + new modification
        # -----------------------------------------------------

        # Prioritize conversation["current_search"] as it contains cumulative refinements (e.g. 2+ years exp)
        current_conversation_search = conversation.get("current_search")
        if current_conversation_search:
            previous_search_for_merge = deepcopy(current_conversation_search)
        else:
            previous_search_for_merge = deepcopy(previous_search or {})

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

        parsed_search = parsed.get("parsed_search") or {}

        logger.info(
            "Modification parsed search: %s",
            parsed_search,
        )

        merged_search = self.context_merger.merge(
            previous_search_for_merge,
            parsed_search,
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

        self.search_repository.update_search(
            conversation["search_id"],
            {"parsed_search": merged_search},
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

    def extract_location_modification(
        self,
        prompt: str,
    ):
        if not prompt:
            return None

        text = prompt.strip()
        lower = text.lower()

        role_keywords = [
            "developer",
            "developers",
            "engineer",
            "engineers",
            "manager",
            "managers",
            "lead",
            "architect",
            "designer",
            "consultant",
            "analyst",
            "director",
            "specialist",
            "scientist",
            "scientists",
        ]
        if any(
            re.search(r"\b" + kw + r"\b", lower)
            for kw in role_keywords
        ):
            return None

        # Check negative location patterns first (allowing commas, hyphens, slashes)
        neg_patterns = [
            r"(?:give\s+(?:me\s+)?)?(?:candidates?\s+)?(?:who\s+are\s+)?(?:not\s+in|outside|not\s+from|exclude\s+location|exclude|except|not\s+located\s+in|not\s+based\s+in)\s+([a-zA-Z0-9\s,\-/]+?)(?:\s+candidates?|\s+profiles?|\s+location)?$",
            r"^(?:candidates?\s+)?(?:who\s+are\s+)?not\s+in\s+([a-zA-Z0-9\s,\-/]+?)(?:\s+candidates?|\s+profiles?|\s+location)?$",
            r"^(?:give\s+)?not\s+in\s+([a-zA-Z0-9\s,\-/]+?)(?:\s+candidates?|\s+profiles?|\s+location)?$",
            r"^([a-zA-Z0-9\s,\-/]+?)\s+not\s+in\s+location$",
            r"^location\s*[:\s]\s*not\s+in\s+([a-zA-Z0-9\s,\-/]+)$",
        ]
        for pattern in neg_patterns:
            match = re.search(pattern, lower)
            if match:
                loc = match.group(1).strip()
                loc = re.sub(r"^(?:the\s+)", "", loc).strip()
                loc = re.sub(r"\s+(?:candidates?|profiles?|resumes?|location)$", "", loc).strip()
                loc = re.sub(r"[,\-/]+$", "", loc).strip()
                if loc and len(loc) >= 2 and loc not in [
                    "candidates",
                    "profiles",
                    "resumes",
                    "ai",
                    "ml",
                    "python",
                    "java",
                ]:
                    return f"NOT {loc.title()}"

        match = re.search(
            r"(?:give\s+me\s+)?(?:candidates?\s+)?(?:who\s+are\s+)?(?:in|from|located\s+in|based\s+in)\s+([a-zA-Z0-9\s,\-/]+?)(?:\s+candidates?|\s+profiles?|\s+location)?$",
            lower,
        )
        if match:
            loc = match.group(1).strip()
            loc = re.sub(r"^(?:the\s+)", "", loc).strip()
            loc = re.sub(r"\s+(?:candidates?|profiles?|resumes?|location)$", "", loc).strip()
            loc = re.sub(r"[,\-/]+$", "", loc).strip()
            if loc and len(loc) >= 2 and loc not in [
                "candidates",
                "profiles",
                "resumes",
            ]:
                return loc.title()

        match = re.search(
            r"^([a-zA-Z0-9\s,\-/]+?)\s+location$",
            lower,
        )
        if match:
            loc = match.group(1).strip()
            loc = re.sub(r"\s+(?:candidates?|profiles?|resumes?)$", "", loc).strip()
            loc = re.sub(r"[,\-/]+$", "", loc).strip()
            if loc and len(loc) >= 2 and loc not in [
                "candidates",
                "profiles",
                "resumes",
            ]:
                return loc.title()

        match = re.search(
            r"^location\s*[:\s]\s*([a-zA-Z0-9\s,\-/]+)$",
            lower,
        )
        if match:
            loc = match.group(1).strip()
            loc = re.sub(r"\s+(?:candidates?|profiles?|resumes?)$", "", loc).strip()
            loc = re.sub(r"[,\-/]+$", "", loc).strip()
            if loc and len(loc) >= 2:
                return loc.title()

        match = re.search(
            r"^(?:only\s+)?([a-zA-Z0-9\s,\-/]+?)\s+(?:candidates?|profiles?)$",
            lower,
        )
        if match:
            loc = match.group(1).strip()
            loc = re.sub(r"[,\-/]+$", "", loc).strip()
            if loc and len(loc) >= 2 and loc not in [
                "ai",
                "ml",
                "python",
                "java",
                "react",
                "angular",
                "node",
                "aws",
                "docker",
            ]:
                return loc.title()

        # Bare location phrases (e.g. "hitech city hyderabad", "give me hitech city hyderabad", "hyderabad", "bangalore")
        non_location_terms = {
            "python", "java", "react", "angular", "node", "nodejs", "aws", "docker",
            "kubernetes", "c++", "c#", ".net", "dotnet", "php", "ruby", "golang",
            "sql", "nosql", "mongodb", "postgresql", "mysql", "devops", "cloud",
            "ml", "ai", "machine", "learning", "data", "science",
            "experience", "experienced", "years", "year", "yrs", "yr",
            "shortlist", "shortlisted", "reject", "rejected", "undo", "status",
            "fresher", "intern", "contract", "fulltime", "parttime",
        }
        if not any(re.search(r"\b" + re.escape(term) + r"\b", lower) for term in non_location_terms):
            clean_bare = lower
            clean_bare = re.sub(r"^(?:give\s+(?:me\s+)?|show\s+(?:me\s+)?|find\s+(?:me\s+)?|get\s+(?:me\s+)?|display\s+|i\s+want\s+|looking\s+for\s+)", "", clean_bare).strip()
            clean_bare = re.sub(r"\s+(?:candidates?|profiles?|resumes?|people|location)$", "", clean_bare).strip()
            clean_bare = re.sub(r"^(?:candidates?\s+)?(?:who\s+are\s+)?(?:in|from|located\s+in|based\s+in)\s+", "", clean_bare).strip()
            clean_bare = re.sub(r"^[,\-.:;]+|[,\-.:;]+$", "", clean_bare).strip()

            known_cities_localities = {
                "hyderabad", "bangalore", "bengaluru", "chennai", "pune", "mumbai",
                "delhi", "new delhi", "noida", "greater noida", "gurgaon", "gurugram",
                "kolkata", "ahmedabad", "kochi", "cochin", "trivandrum", "thiruvananthapuram",
                "coimbatore", "chandigarh", "indore", "jaipur", "bhubaneswar", "visakhapatnam", "vizag",
                "hitech city", "hi-tech city", "hitec city", "hi tech city", "hitech", "hitec",
                "gachibowli", "madhapur", "kondapur", "kukatpally", "jubilee hills", "banjara hills",
                "financial district", "whitefield", "electronic city", "koramangala", "indiranagar",
                "manyata", "bellandur", "marathahalli", "hinjewadi", "magarpatta", "kharadi",
                "singapore", "london", "dubai", "new york", "san francisco", "seattle", "austin", "toronto",
            }
            if clean_bare:
                norm_bare = re.sub(r"[,\-_/\\|;:.()]+", " ", clean_bare).strip()
                words = norm_bare.split()
                if (
                    norm_bare in known_cities_localities
                    or any(loc in norm_bare for loc in known_cities_localities)
                    or (words and all(w in known_cities_localities or w in {"city", "area", "district", "region", "town", "hub", "in", "and", "near"} for w in words))
                ):
                    return clean_bare.title()

        return None

    def extract_role_modification(
        self,
        prompt: str,
    ):
        if not prompt:
            return None

        text = prompt.strip()
        lower = text.lower()

        # If it's experience-related, don't treat as role
        if re.search(r"\b\d+\+?\s*(?:years?|yrs?)\b", lower):
            return None

        # If it's location-related, don't treat as role
        if self.extract_location_modification(prompt):
            return None

        # If it's status or control command, don't treat as role
        if re.search(r"\b(?:reset|shortlisted?|rejected?|undo|clear|start\s+over)\b", lower):
            return None

        cleaned = lower
        cleaned = re.sub(
            r"^(?:give\s+(?:me\s+)?|show\s+(?:me\s+)?|find\s+(?:me\s+)?|get\s+(?:me\s+)?|display\s+|i\s+want\s+|looking\s+for\s+)",
            "",
            cleaned,
        ).strip()
        cleaned = re.sub(r"^(?:only\s+|just\s+|filter\s+by\s+|refine\s+by\s+)", "", cleaned).strip()
        cleaned = re.sub(r"^(?:candidates?\s+)?(?:who\s+are\s+)", "", cleaned).strip()
        cleaned = re.sub(r"\s+(?:only)$", "", cleaned).strip()
        cleaned = re.sub(r"\s+(?:candidates?|profiles?|resumes?|people)$", "", cleaned).strip()
        cleaned = re.sub(r"^(?:role|title|designation)\s*[:\s]\s*", "", cleaned).strip()

        role_suffix_pattern = r"\b(?:engineers?|developers?|programmers?|architects?|scientists?|analysts?|leads?|managers?|designers?|specialists?|directors?|administrators?|consultants?|sde|swe)\b"
        if re.search(role_suffix_pattern, cleaned):
            words = cleaned.split()
            if 1 <= len(words) <= 5:
                clean_title = re.sub(r"s$", "", cleaned) if cleaned.endswith("s") and not cleaned.endswith("ss") else cleaned
                return clean_title.title()

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

    def _resolve_candidate_for_reasoning(
        self,
        search_id: str,
        parsed: dict,
        prompt: str,
        conversation: dict,
    ):
        raw_name = (parsed.get("candidate_name") or "").strip() if parsed else ""
        generic_terms = {
            "he", "him", "his", "she", "her", "hers", "they", "them", "their",
            "this", "that", "it", "candidate", "the candidate", "this candidate",
            "selected", "shortlisted", "selected candidate", "shortlisted candidate",
            "he selected", "she selected"
        }

        # 1. Check if an explicit candidate name was provided and is not a generic/pronoun
        if raw_name and raw_name.lower() not in generic_terms:
            cand = self.search_service.search_repository.get_candidate_by_name(
                search_id=search_id,
                candidate_name=raw_name,
            )
            if cand:
                return cand

            # Clean trailing question / filler words (e.g. "Rahul selected" -> "Rahul")
            cleaned_name = re.sub(
                r"\b(is|was|selected|shortlisted|candidate|developer|engineer|profile|good\s+match|match)\b",
                "",
                raw_name,
                flags=re.IGNORECASE,
            ).strip()
            if cleaned_name and cleaned_name.lower() not in generic_terms:
                cand = self.search_service.search_repository.get_candidate_by_name(
                    search_id=search_id,
                    candidate_name=cleaned_name,
                )
                if cand:
                    return cand

        # 2. Check if any candidate name in current search_results appears in the user prompt
        all_candidates = list(
            self.search_repository.search_results.find(
                {"search_id": search_id}
            ).sort("rank", 1)
        )

        if prompt and all_candidates:
            for c in all_candidates:
                full_name = (c.get("candidate_name") or "").strip()
                if not full_name:
                    continue
                # Full name match in prompt
                if re.search(rf"\b{re.escape(full_name)}\b", prompt, re.IGNORECASE):
                    return c
                # First name match in prompt (if >= 3 characters)
                first_name = full_name.split()[0]
                if len(first_name) >= 3 and first_name.lower() not in generic_terms:
                    if re.search(rf"\b{re.escape(first_name)}\b", prompt, re.IGNORECASE):
                        return c

        # 3. Contextual resolution (for pronouns "why he selected", "why was he selected", etc.)
        # A. Check conversation history for recently actioned / mentioned candidate
        messages = conversation.get("messages", []) if conversation else []
        for msg in reversed(messages):
            content = msg.get("content")
            if isinstance(content, dict):
                c_name = content.get("candidate_name")
                if c_name and c_name.lower() not in generic_terms:
                    cand = self.search_service.search_repository.get_candidate_by_name(
                        search_id=search_id,
                        candidate_name=c_name,
                    )
                    if cand:
                        return cand
                pid = content.get("profile_id")
                if pid:
                    cand = self.search_repository.get_candidate(search_id, pid)
                    if cand:
                        return cand
            elif isinstance(content, str):
                for c in all_candidates:
                    c_name = (c.get("candidate_name") or "").strip()
                    if c_name and re.search(rf"\b{re.escape(c_name)}\b", content, re.IGNORECASE):
                        return c

        # B. Check if any candidate has status "SHORTLISTED"
        shortlisted = [c for c in all_candidates if c.get("status") == "SHORTLISTED"]
        if shortlisted:
            return shortlisted[0]

        # C. Default to top-ranked candidate (rank 1)
        if all_candidates:
            return all_candidates[0]

        return None

    def candidate_reasoning(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):
        search_id = conversation.get("search_id") or request.search_id
        conversation_message_id = conversation.get("conversation_message_id")

        if not search_id:
            err_response = {
                "success": False,
                "type": "CANDIDATE_REASONING",
                "search_id": "",
                "conversation_message_id": conversation_message_id,
                "message": "Please perform a search first.",
                "results": [],
                "total_candidates": 0,
            }
            if conversation_message_id:
                self.conversation_message_repository.update_message(
                    message_id=conversation_message_id,
                    assistant_message=err_response,
                )
            self.conversation_service.add_assistant_message(
                conversation=conversation,
                message=err_response,
                conversation_message_id=conversation_message_id,
            )
            return err_response

        candidate = self._resolve_candidate_for_reasoning(
            search_id=search_id,
            parsed=parsed,
            prompt=request.prompt,
            conversation=conversation,
        )

        candidate_name = (parsed.get("candidate_name") or "").strip() if parsed else ""

        if candidate is None:
            msg = (
                f"Candidate '{candidate_name}' not found."
                if candidate_name
                else "No candidate found in current search to explain reasoning."
            )
            err_response = {
                "success": False,
                "type": "CANDIDATE_REASONING",
                "search_id": search_id,
                "conversation_message_id": conversation_message_id,
                "message": msg,
                "results": [],
                "total_candidates": 0,
            }
            if conversation_message_id:
                self.conversation_message_repository.update_message(
                    message_id=conversation_message_id,
                    assistant_message=err_response,
                )
            self.conversation_service.add_assistant_message(
                conversation=conversation,
                message=err_response,
                conversation_message_id=conversation_message_id,
            )
            return err_response

        profile_id = candidate["profile_id"]
        logger.info(
            f"Generating reasoning for candidate: {candidate.get('candidate_name')} (profile_id={profile_id})"
        )

        response_data = (
            self.search_service
            .get_candidate_reasoning(
                search_id=search_id,
                profile_id=profile_id,
            )
        )

        reasoning = (
            response_data.get("reasoning")
            or response_data.get("message")
            or ""
        )

        # Update candidate in-memory fields
        candidate["reasoning"] = reasoning
        candidate["reasoning_generated"] = True
        if "_id" in candidate:
            candidate["_id"] = str(candidate["_id"])

        response = {
            "success": True,
            "type": "CANDIDATE_REASONING",
            "search_id": search_id,
            "conversation_message_id": conversation_message_id,
            "candidate_name": candidate.get("candidate_name", ""),
            "profile_id": profile_id,
            "reasoning": reasoning,
            "message": reasoning,
            "answer": reasoning,
            "candidate": candidate,
            "results": [candidate],
            "total_candidates": 1,
            "count": 1,
            "page": 1,
            "page_size": page_size,
        }

        if conversation_message_id:
            self.conversation_message_repository.update_message(
                message_id=conversation_message_id,
                assistant_message={
                    "type": "CANDIDATE_REASONING",
                    "candidate_name": candidate.get("candidate_name"),
                    "profile_id": profile_id,
                    "message": reasoning,
                    "reasoning": reasoning,
                    "total_candidates": 1,
                },
            )

        self.conversation_service.add_assistant_message(
            conversation=conversation,
            message={
                "type": "CANDIDATE_REASONING",
                "candidate_name": candidate.get("candidate_name"),
                "profile_id": profile_id,
                "message": reasoning,
                "reasoning": reasoning,
                "results": 1,
            },
            conversation_message_id=conversation_message_id,
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

        conversation["current_search"] = {}
        conversation["latest_search_id"] = None

        self.conversation_service.save(
            conversation["search_id"],
            conversation,
        )

        message_text = "Search criteria have been reset. You can start a fresh search."

        if conversation.get("conversation_message_id"):
            self.conversation_message_repository.update_message(
                message_id=conversation["conversation_message_id"],
                assistant_message={
                    "type": "RESET_SEARCH",
                    "message": message_text,
                },
            )

        self.conversation_service.add_assistant_message(
            conversation,
            {
                "type": "RESET_SEARCH",
                "message": message_text,
            },
        )

        return {
            "type": "RESET_SEARCH",
            "message": message_text,
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
        search_id = conversation.get("search_id") or request.search_id
        response = (
            self.candidate_action_service.shortlist(
                search_id=search_id,
                candidate_name=parsed.get("candidate_name", ""),
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
        search_id = conversation.get("search_id") or request.search_id
        response = (
            self.candidate_action_service.reject(
                search_id=search_id,
                candidate_name=parsed.get("candidate_name", ""),
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
        search_id = conversation.get("search_id") or request.search_id

        job_target = None
        if parsed and parsed.get("job_position"):
            job_target = parsed.get("job_position")
        elif request.job_position_id:
            job_pos_doc = self.job_position_repository.get_job_position(request.job_position_id)
            if job_pos_doc:
                job_target = job_pos_doc.get("title")
        if not job_target and request.prompt:
            match = re.search(
                r"shortlisted\s+(?:candidates?\s+)?(?:for|in|as|under)\s+([a-zA-Z0-9_\s\-/]+)",
                request.prompt,
                re.IGNORECASE,
            )
            if match:
                job_target = match.group(1).strip()
                job_target = re.sub(r"\s+(?:candidates?|profiles?)$", "", job_target, flags=re.IGNORECASE).strip()

        data = self.candidate_action_service.shortlisted(
            search_id=search_id,
            job_position=job_target,
        )

        results = data.get("results", []) if isinstance(data, dict) else (data or [])
        total_candidates = len(results)
        total_pages = (total_candidates + page_size - 1) // page_size if page_size > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size

        response = {
            "search_id": search_id,
            "conversation_message_id": conversation.get("conversation_message_id"),
            "page": page,
            "page_size": page_size,
            "total_candidates": total_candidates,
            "total_pages": total_pages,
            "count": total_candidates,
            "results": results[start:end],
        }

        if conversation.get("conversation_message_id"):
            self.conversation_message_repository.update_message(
                message_id=conversation["conversation_message_id"],
                assistant_message={
                    "type": "SHOW_SHORTLISTED",
                    "total_candidates": total_candidates,
                },
            )
            self.conversation_service.add_assistant_message(
                conversation=conversation,
                message={
                    "type": "SHOW_SHORTLISTED",
                    "results": total_candidates,
                },
                conversation_message_id=conversation["conversation_message_id"],
            )

        return response

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
        search_id = conversation.get("search_id") or request.search_id

        job_target = None
        if parsed and parsed.get("job_position"):
            job_target = parsed.get("job_position")
        elif request.job_position_id:
            job_pos_doc = self.job_position_repository.get_job_position(request.job_position_id)
            if job_pos_doc:
                job_target = job_pos_doc.get("title")
        if not job_target and request.prompt:
            match = re.search(
                r"rejected\s+(?:candidates?\s+)?(?:for|in|as|under)\s+([a-zA-Z0-9_\s\-/]+)",
                request.prompt,
                re.IGNORECASE,
            )
            if match:
                job_target = match.group(1).strip()
                job_target = re.sub(r"\s+(?:candidates?|profiles?)$", "", job_target, flags=re.IGNORECASE).strip()

        data = self.candidate_action_service.rejected(
            search_id=search_id,
            job_position=job_target,
        )

        results = data.get("results", []) if isinstance(data, dict) else (data or [])
        total_candidates = len(results)
        total_pages = (total_candidates + page_size - 1) // page_size if page_size > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size

        response = {
            "search_id": search_id,
            "conversation_message_id": conversation.get("conversation_message_id"),
            "page": page,
            "page_size": page_size,
            "total_candidates": total_candidates,
            "total_pages": total_pages,
            "count": total_candidates,
            "results": results[start:end],
        }

        if conversation.get("conversation_message_id"):
            self.conversation_message_repository.update_message(
                message_id=conversation["conversation_message_id"],
                assistant_message={
                    "type": "SHOW_REJECTED",
                    "total_candidates": total_candidates,
                },
            )
            self.conversation_service.add_assistant_message(
                conversation=conversation,
                message={
                    "type": "SHOW_REJECTED",
                    "results": total_candidates,
                },
                conversation_message_id=conversation["conversation_message_id"],
            )

        return response

    # =========================================================
    # SHOW CANDIDATES (CURRENT SEARCH RESULTS WITH LIVE STATUS)
    # =========================================================

    def show_candidates(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):
        search_id = conversation.get("search_id") or request.search_id

        # 1. Fetch latest candidates
        candidates = self.search_repository.get_latest_search_results(search_id)

        # 2. Fallback if not found via latest_search_id
        if not candidates:
            messages = conversation.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = msg.get("content")
                    if isinstance(content, dict) and content.get("conversation_message_id"):
                        candidates = self.search_repository.get_results_by_conversation_message(
                            content["conversation_message_id"],
                            search_id=search_id,
                        )
                        if candidates:
                            break

        # Fallback 3: check search_results directly
        if not candidates and search_id:
            latest_doc = self.search_repository.search_results.find_one(
                {"search_id": search_id}, sort=[("created_at", -1)]
            )
            if latest_doc and latest_doc.get("conversation_message_id"):
                candidates = self.search_repository.get_results_by_conversation_message(
                    latest_doc["conversation_message_id"],
                    search_id=search_id,
                )

        # 3. Synchronize live status from both search_results and job_vs_candidates
        try:
            shortlisted_pids = set()
            rejected_pids = set()

            if search_id:
                sr_shortlisted = self.search_repository.get_shortlisted_profile_ids(search_id)
                shortlisted_pids.update(sr_shortlisted)
                sr_rejected = {
                    r.get("profile_id")
                    for r in self.search_repository.search_results.find(
                        {"search_id": search_id, "status": "REJECTED"},
                        {"profile_id": 1}
                    )
                    if r.get("profile_id")
                }
                rejected_pids.update(sr_rejected)

                shortlisted_records = self.job_vs_candidate_repository.get_shortlisted_candidates(search_id)
                shortlisted_pids.update(r.get("profile_id") for r in shortlisted_records if r.get("profile_id"))
                rejected_records = self.job_vs_candidate_repository.get_rejected_candidates(search_id)
                rejected_pids.update(r.get("profile_id") for r in rejected_records if r.get("profile_id"))

            for cand in candidates:
                pid = cand.get("profile_id")
                if pid in shortlisted_pids:
                    cand["status"] = "SHORTLISTED"
                elif pid in rejected_pids:
                    cand["status"] = "REJECTED"
                elif not cand.get("status"):
                    cand["status"] = "PENDING"
        except Exception as e:
            logger.warning(f"Error syncing status: {e}")

        total_candidates = len(candidates)
        total_pages = (total_candidates + page_size - 1) // page_size if page_size > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size

        response = {
            "search_id": search_id,
            "conversation_message_id": conversation.get("conversation_message_id"),
            "page": page,
            "page_size": page_size,
            "total_candidates": total_candidates,
            "total_pages": total_pages,
            "count": total_candidates,
            "results": candidates[start:end],
        }

        # 4. Record assistant message in conversation
        if conversation.get("conversation_message_id"):
            self.conversation_message_repository.update_message(
                message_id=conversation["conversation_message_id"],
                assistant_message={
                    "type": "SEARCH",
                    "total_candidates": total_candidates,
                },
            )
            self.conversation_service.add_assistant_message(
                conversation=conversation,
                message={
                    "type": "SEARCH",
                    "results": total_candidates,
                },
                conversation_message_id=conversation["conversation_message_id"],
            )

        return response

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
        search_id = conversation.get("search_id") or request.search_id
        response = (
            self.candidate_action_service
            .undo_shortlist(
                search_id=search_id,
                candidate_name=
                    parsed.get("candidate_name", ""),
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
        search_id = conversation.get("search_id") or request.search_id
        response = (
            self.candidate_action_service
            .undo_reject(
                search_id=search_id,
                candidate_name=
                    parsed.get("candidate_name", ""),
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

            if not candidates and message.get("intent") == "CANDIDATE_REASONING":
                asst_msg = message.get("assistant_message")
                if isinstance(asst_msg, dict) and asst_msg.get("profile_id"):
                    cand = self.search_repository.get_candidate(
                        search_id=search_id,
                        profile_id=asst_msg["profile_id"],
                    )
                    if cand:
                        candidates = [cand]

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
