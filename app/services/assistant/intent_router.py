from app.config.logging import logger
from fastapi import HTTPException
class IntentRouter:

    def route(
        self,
        assistant,
        intent,
        conversation,
        parsed,
        job_position,
        request,
        page,
        page_size,
    ):

        # Override SEARCH -> SEARCH_MODIFICATION when a search already exists

        # Detect search modification only when there is an active search
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

                # Existing search + no explicit reset -> treat as modification
                if not is_explicit_new_search:
                    intent = "SEARCH_MODIFICATION"

        logger.info("=" * 80)
        logger.info(f"Routing Intent : {intent}")
        logger.info("=" * 80)

        # -----------------------------
        # SEARCH VALIDATION
        # -----------------------------
        if intent == "SEARCH":

            # Global search is allowed without a job position
            if request.global_search_allowed and not request.job_position_id:
                request.job_position_id = None

            # Job-based search
            elif not request.job_position_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "job_position_id is required when "
                        "global_search_allowed is false."
                    ),
                )



        handlers = {
            "SEARCH": assistant.handle_search,
            "SEARCH_MODIFICATION": assistant.modify_search,
            "GENERAL": assistant.answer_general,
            "SEARCH_HISTORY": assistant.search_history,
            "COMPARE_CANDIDATES": assistant.compare_candidates,
            "CANDIDATE_REASONING": assistant.candidate_reasoning,
            "RESET_SEARCH": assistant.reset_search,
            "SHORTLIST": assistant.shortlist_candidate,
            "REJECT": assistant.reject_candidate,
            "SHOW_SHORTLISTED": assistant.show_shortlisted,
            "SHOW_REJECTED": assistant.show_rejected,
            "UNDO_SHORTLIST": assistant.undo_shortlist,
            "UNDO_REJECT": assistant.undo_reject,
        }
        handler = handlers.get(
            intent,
            assistant.unknown_intent,
        )

        if intent in ["SEARCH", "SEARCH_MODIFICATION"]:

            return handler(
                conversation=conversation,
                parsed=parsed,
                job_position=job_position,
                request=request,
                page=page,
                page_size=page_size,
            )

        return handler(
            conversation=conversation,
            parsed=parsed,
            request=request,
            page=page,
            page_size=page_size,
        )