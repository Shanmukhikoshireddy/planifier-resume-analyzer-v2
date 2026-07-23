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

class AssistantService:

    def __init__(self):

        self.conversation_service = ConversationService()

        self.prompt_parser = PromptParserService()

        self.search_service = SearchService()

        self.context_builder = ContextBuilder()

        self.openai_service = OpenAIService()

        self.intent_router = IntentRouter()
        self.candidate_action_service = CandidateActionService()

    # Main Entry

    def process(
        self,
        request,
        page,
        page_size,
    ):

        # Load/Create Conversation

        if request.job_id:

            conversation = self.conversation_service.load(
                request.job_id
            )

            if conversation is None:

                conversation = self.conversation_service.create()

        else:

            conversation = self.conversation_service.create()

        # Parse Prompt

        parsed = self.prompt_parser.parse(
            request.prompt,
        )

        # Store User Message

        self.conversation_service.add_user_message(
            conversation,
            request.prompt,
        )

        # Route Intent

        try:
            return self.intent_router.route(
                assistant=self,
                intent=parsed["intent"],
                conversation=conversation,
                parsed=parsed,
                request=request,
                page=page,
                page_size=page_size,
            )
        except Exception:
            print(traceback.format_exc())
            raise

    # Build Search Context

    def build_search_context(
        self,
        conversation,
        merged_job,
        request,
        is_new_search,
    ):

        return {

            "job_id": conversation["job_id"],

            "job": merged_job,

            "job_position": request.job_position,

            "received_within": request.received_within,

            "original_prompt": request.prompt,

            "is_new_search": is_new_search,

        }

    # Execute Search

    def execute_search(
        self,
        conversation,
        merged_job,
        request,
        page,
        page_size,
        is_new_search,
        message_type,
    ):

        search_context = self.build_search_context(

            conversation,

            merged_job,

            request,

            is_new_search,

        )

        response = self.search_service.execute(

            search_context,

            page,

            page_size,

        )

        self.conversation_service.update_latest_search(

            conversation,

            response["job_id"],

        )

        self.conversation_service.add_assistant_message(

            conversation,

            {

                "type": message_type,

                "results": response["total_candidates"],

            },

        )

        return response

    # SEARCH

    def handle_search(
        self,
        conversation,
        parsed,
        request,
        page,
        page_size,
    ):

        merged_job = self.conversation_service.merge_job(

            conversation,

            parsed["job"],

        )

        return self.execute_search(

            conversation=conversation,

            merged_job=merged_job,

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
        page,
        page_size,
    ):

        merged_job = self.conversation_service.merge_job(

            conversation,

            parsed["job"],

        )

        return self.execute_search(

            conversation=conversation,

            merged_job=merged_job,

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

        if not request.job_id:

            return {
                "success": False,
                "message": "Please perform a search first."
            }

        candidate = self.search_service.search_repository.get_candidate_by_name(

            job_id=request.job_id,

            candidate_name=parsed["candidate_name"],

        )

        if candidate is None:

            return {

                "success": False,

                "message": f"Candidate '{parsed['candidate_name']}' not found."

            }

        response = self.search_service.get_candidate_reasoning(

            job_id=request.job_id,

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

            job_id=request.job_id,

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

            job_id=request.job_id,

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

            request.job_id,

        )

        return {

            "job_id": request.job_id,

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

            request.job_id,

        )

        return {

            "job_id": request.job_id,

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
            job_id=request.job_id,
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

            job_id=request.job_id,

            candidate_name=parsed["candidate_name"],

        )

        self.conversation_service.add_assistant_message(

            conversation,

            response,

        )

        return response
    
