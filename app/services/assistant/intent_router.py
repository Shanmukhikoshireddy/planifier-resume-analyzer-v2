from app.config.logging import logger


class IntentRouter:

    def route(
        self,
        assistant,
        intent: str,
        conversation: dict,
        parsed: dict,
        request,
        page: int,
        page_size: int,
    ):

        # ------------------------------------------------------------------
        # Override SEARCH -> SEARCH_MODIFICATION when a search already exists
        # ------------------------------------------------------------------

        if intent == "SEARCH":

            current_job = conversation.get("current_job")

            if current_job:

                prompt = request.prompt.lower()

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

        logger.info("=" * 80)
        logger.info(f"Routing Intent : {intent}")
        logger.info("=" * 80)

        handlers = {

            "SEARCH":
                assistant.handle_search,

            "SEARCH_MODIFICATION":
                assistant.modify_search,

            "GENERAL":
                assistant.answer_general,

            "SEARCH_HISTORY":
                assistant.search_history,

            "COMPARE_CANDIDATES":
                assistant.compare_candidates,

            "CANDIDATE_REASONING": 
                assistant.candidate_reasoning,

            "RESET_SEARCH":
                assistant.reset_search,
            "SHORTLIST":
                assistant.shortlist_candidate,

            "REJECT":
                assistant.reject_candidate,

            "SHOW_SHORTLISTED":
                assistant.show_shortlisted,

            "SHOW_REJECTED":
                assistant.show_rejected,

            "UNDO_SHORTLIST":
                assistant.undo_shortlist,

            "UNDO_REJECT":
                assistant.undo_reject,

        }

        handler = handlers.get(
            intent,
            assistant.unknown_intent,
        )

        return handler(

            conversation=conversation,

            parsed=parsed,

            request=request,

            page=page,

            page_size=page_size,

        )