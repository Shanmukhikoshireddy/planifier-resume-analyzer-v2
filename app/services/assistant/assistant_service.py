from app.services.assistant.conversation_service import ConversationService
from app.services.assistant.context_builder import ContextBuilder
from app.services.assistant.intent_router import IntentRouter
from app.services.search.search_service import SearchService
from app.config.logging import logger
from app.services.shared.openai_service import OpenAIService
import traceback
from app.services.orchestrator.prompt_parser_service import (
    PromptParserService,
)
from app.services.candidate.candidate_action_service import CandidateActionService
from app.repository.conversation_message_repository import ConversationMessageRepository
from app.repository.search_repository import SearchRepository
from app.repository.job_position_repository import JobPositionRepository

class AssistantService:

    def __init__(self):

        self.conversation_service = ConversationService()

        self.prompt_parser = PromptParserService()

        self.search_service = SearchService()

        self.context_builder = ContextBuilder()

        self.openai_service = OpenAIService()
        
        self.job_position_repository = JobPositionRepository()

        self.intent_router = IntentRouter()
        self.candidate_action_service = CandidateActionService()
        self.conversation_message_repository = ConversationMessageRepository()
        self.search_repository = SearchRepository()

    # Main Entry


    def process(
        self,
        request,
        page,
        page_size,
    ):

        # -------------------------------------------------------
        # Load / Create Conversation
        # -------------------------------------------------------

        if request.search_id:

            conversation = self.conversation_service.load(
                request.search_id
            )

            if conversation is None:
                conversation = self.conversation_service.create()

        else:

            conversation = self.conversation_service.create()

        # -------------------------------------------------------
        # Detect Intent
        # -------------------------------------------------------

        intent_result = self.prompt_parser.detect_intent(
            request.prompt
        )

        intent = intent_result["intent"]

        logger.info(f"Detected Intent : {intent}")

        if intent == "SEARCH":

            current_search = conversation.get("current_search")

            if current_search:

                prompt = request.prompt.lower().strip()

                new_search_keywords = [
                    "new search",
                    "start new search",
                    "reset search",
                    "clear search",
                    "fresh search",
                ]

                is_explicit_new_search = any(
                    keyword in prompt
                    for keyword in new_search_keywords
                )

                if not is_explicit_new_search:
                    intent = "SEARCH_MODIFICATION"

        logger.info(f"Final Intent : {intent}")

        # -------------------------------------------------------
        # Default values
        # -------------------------------------------------------

        job_position = None

        # -------------------------------------------------------
        # SEARCH / SEARCH MODIFICATION
        # -------------------------------------------------------

        if intent in ["SEARCH", "SEARCH_MODIFICATION"]:

            # ---------------------------------------
            # SEARCH MODIFICATION
            # ---------------------------------------

            if intent == "SEARCH_MODIFICATION":

                search = self.search_repository.get_search(
                    request.search_id
                )

                if search is None:
                    raise Exception("Search not found.")

                search_result = self.prompt_parser.parse_search(
                    request.prompt
                )

                parsed = {
                    "intent": intent,
                    "parsed_search": search_result["job"],
                }

            # ---------------------------------------
            # NEW SEARCH
            # ---------------------------------------

            else:

                # Global Search
                if request.global_search_allowed:

                    job_position = None

                    merged_prompt = request.prompt

                # Job-based Search
                else:

                    if not request.job_position_id:
                        raise Exception(
                            "job_position_id is required when global_search_allowed is false."
                        )

                    job_position = self.job_position_repository.get_job_position(
                        request.job_position_id
                    )

                    if job_position is None:
                        raise Exception("Job Position not found.")

                    merged_prompt = f"""
    Job Description:

    {job_position.get("jobDescription", "")}

    Recruiter Instructions:

    {request.prompt}
    """

                search_result = self.prompt_parser.parse_search(
                    merged_prompt
                )

                parsed = {
                    "intent": intent,
                    "parsed_search": search_result["job"],
                }

        else:

            parsed = intent_result

        # -------------------------------------------------------
        # Save User Message
        # -------------------------------------------------------

        conversation_message_id = (
            self.conversation_message_repository.create_message(
                search_id=conversation["search_id"],
                user_prompt=request.prompt,
                intent=parsed["intent"],
            )
        )

        conversation["conversation_message_id"] = (
            conversation_message_id
        )

        self.conversation_service.add_user_message(
            conversation,
            request.prompt,
        )

        # -------------------------------------------------------
        # Route Intent
        # -------------------------------------------------------

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

            logger.exception("Assistant routing failed.")

            raise
    # Build Search Context

    def build_search_context(
        self,
        conversation,
        parsed_search,
        job_position,
        request,
        is_new_search,
    ):

        return {

            "search_id": conversation["search_id"],

            "job_position_id":
                str(job_position["_id"])
                if job_position
                else None,

            "job_description":
                job_position["jobDescription"]
                if job_position
                else None,

            "parsed_search": parsed_search,

            "original_prompt": request.prompt,

            "received_within": request.received_within,

            "global_search_allowed": request.global_search_allowed,

            "is_new_search": is_new_search,

        }

    # Execute Search

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

        search_context = self.build_search_context(
            conversation=conversation,
            parsed_search=merged_search,
            job_position=job_position,
            request=request,
            is_new_search=is_new_search,
        )

        response = self.search_service.execute(

            search_context,

            page,

            page_size,
            conversation["conversation_message_id"],

        )
        self.conversation_message_repository.update_message(
            message_id=conversation["conversation_message_id"],
            assistant_message={
                "type": message_type,
                "total_candidates": response["total_candidates"],
            },
        )

        self.conversation_service.update_latest_search(

            conversation,

            conversation["conversation_message_id"],

        )
        

        self.conversation_service.add_assistant_message(

            conversation=conversation,

            message={

                "type": message_type,

                "results": response["total_candidates"],

            },

            conversation_message_id=conversation[
                "conversation_message_id"
            ],

        )

        return response

    # SEARCH

    def handle_search(
        self,
        conversation,
        parsed,
        job_position,
        request,
        page,
        page_size,
    ):

        merged_search = self.conversation_service.merge_search(

            conversation,

            parsed["parsed_search"],

        )

        return self.execute_search(
            conversation=conversation,
            merged_search=merged_search,
            job_position=job_position,
            request=request,
            page=page,
            page_size=page_size,
            is_new_search=True,
            message_type="SEARCH",
        )

    # SEARCH MODIFICATION

    def modify_search(
        self,
        conversation,
        parsed,
        request,
        job_position,
        page,
        page_size,
    ):

        merged_search = self.conversation_service.merge_search(
            conversation,
            parsed["parsed_search"],
        )

        return self.execute_search(
            conversation=conversation,
            merged_search=merged_search,
            job_position=job_position,
            request=request,
            page=page,
            page_size=page_size,
            is_new_search=False,
            message_type="SEARCH_MODIFICATION",
        )
    # GENERAL QUESTIONS

    def answer_general(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        context = self.context_builder.build()

        conversation_context = self.conversation_service.build_context(

            conversation,

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

        answer = self.openai_service.generate(
            messages,
        )

        self.conversation_service.add_assistant_message(

            conversation,

            answer,

        )

        return {

            "type": "GENERAL",

            "answer": answer,

        }

    # SEARCH HISTORY

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

            "messages": conversation.get(

                "messages",

                [],

            ),

        }

    # COMPARE CANDIDATES

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

    # CANDIDATE REASONING

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
                "message": "Please perform a search first."
            }

        candidate = self.search_service.search_repository.get_candidate_by_name(

            search_id=request.search_id,

            candidate_name=parsed["candidate_name"],

        )

        if candidate is None:

            return {

                "success": False,

                "message": f"Candidate '{parsed['candidate_name']}' not found."

            }

        response = self.search_service.get_candidate_reasoning(

            search_id=request.search_id,

            profile_id=candidate["profile_id"],

        )

        self.conversation_service.add_assistant_message(

            conversation,

            response,

        )

        return response

    # RESET SEARCH

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

            "message": "Not implemented yet.",

        }

    # UNKNOWN INTENT

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
##########
    # Shortlist Candidat##########

    def shortlist_candidate(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        response = self.candidate_action_service.shortlist(

            search_id=request.search_id,

            candidate_name=parsed["candidate_name"],

        )

        self.conversation_service.add_assistant_message(

            conversation,

            response,

        )

        return response
    ##########
    # Reject Candidat##########

    def reject_candidate(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        response = self.candidate_action_service.reject(

            search_id=request.search_id,

            candidate_name=parsed["candidate_name"],

        )

        self.conversation_service.add_assistant_message(

            conversation,

            response,

        )

        return response

    ##########
    # Show Shortliste##########

    def show_shortlisted(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        candidates = self.candidate_action_service.shortlisted(

            request.search_id,

        )

        return {

            "search_id": request.search_id,

            "count": len(candidates),

            "results": candidates,

        }
    ##########
    # Show Rejecte##########

    def show_rejected(
        self,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        candidates = self.candidate_action_service.rejected(

            request.search_id,

        )

        return {

            "search_id": request.search_id,

            "count": len(candidates),

            "results": candidates,

        }
    
    def undo_shortlist(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):
        logger.info(">>> Assistant undo_reject")

        response = self.candidate_action_service.undo_shortlist(
            search_id=request.search_id,
            candidate_name=parsed["candidate_name"],
        )

        self.conversation_service.add_assistant_message(
            conversation,
            response,
        )
        logger.info(">>> Response:", response)

        return response


    def undo_reject(
            self,
            conversation,
            parsed,
            request,
            page,
            page_size,
        ):

        response = self.candidate_action_service.undo_reject(

            search_id=request.search_id,

            candidate_name=parsed["candidate_name"],

        )

        self.conversation_service.add_assistant_message(

            conversation,

            response,

        )

        return response
    def get_conversation_history(
        self,
        search_id: str,
    ):

        messages = (
            self.conversation_message_repository.get_messages(
                search_id,
            )
        )

        history = []

        for message in messages:

            candidates = (
                self.search_repository.get_results_by_conversation_message(
                    message["_id"],
                )
            )

            history.append(
                {
                    "conversation_message_id": message["_id"],
                    "user_prompt": message["user_prompt"],
                    "intent": message["intent"],
                    "assistant_message": message["assistant_message"],
                    "candidates": candidates,
                }
            )

        return {
            "search_id": search_id,
            "history": history,
        }
