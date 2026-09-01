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

        logger.info("=" * 80)
        logger.info(f"Routing Intent : {intent}")
        logger.info("=" * 80)

        # ---------------------------------------------------------
        # SEARCH VALIDATION
        # ---------------------------------------------------------

        if intent == "SEARCH":

            # -----------------------------------------------------
            # GLOBAL SEARCH ON
            #
            # Job position is optional.
            # -----------------------------------------------------

            if (
                request.global_search_allowed
                and not request.job_position_id
            ):

                request.job_position_id = None

            # -----------------------------------------------------
            # GLOBAL SEARCH OFF
            #
            # Job position is mandatory.
            # -----------------------------------------------------

            elif not request.job_position_id:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Please select a job position "
                        "when Global Search is off."
                    ),
                )

        # ---------------------------------------------------------
        # HANDLERS
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # SEARCH / SEARCH MODIFICATION
        # ---------------------------------------------------------

        if intent in (
            "SEARCH",
            "SEARCH_MODIFICATION",
        ):

            return handler(
                conversation=conversation,
                parsed=parsed,
                job_position=job_position,
                request=request,
                page=page,
                page_size=page_size,
            )

        # ---------------------------------------------------------
        # OTHER INTENTS
        # ---------------------------------------------------------

        return handler(
            conversation=conversation,
            parsed=parsed,
            request=request,
            page=page,
            page_size=page_size,
        )