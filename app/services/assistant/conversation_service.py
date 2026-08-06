from copy import deepcopy
from app.config.logging import logger
from app.repository.search_repository import SearchRepository
from app.utils.context_merger import ContextMerger


class ConversationService:

    def __init__(self):
        self.search_repository = SearchRepository()
        self.context_merger = ContextMerger()

    ###########################################################
    # Load Conversation
    ###########################################################

    def load(
        self,
        search_id: str,
    ):

        conversation = self.search_repository.get_conversation(
            search_id
        )

        if conversation:
            conversation["search_id"] = search_id
            return conversation

        return self.create(search_id)

    ###########################################################
    # Create Empty Conversation
    ###########################################################

    def create(
        self,
    ):
        search_id = self.search_repository.create_empty_search()

        conversation = {
            "search_id": search_id,
            "messages": [],
            "current_search": {},
            "latest_search_id": None,
            "context_summary": "",
        }

        self.save(search_id, conversation)

        return conversation
    ###########################################################
    # Build Context
    ###########################################################

    def build_context(
        self,
        conversation,
    ) -> str:
        """
        Build LLM-friendly conversation context.
        """

        lines = []

        # --------------------------------------------------
        # Current Search Context
        # --------------------------------------------------

        current_search = conversation.get("current_search", {})

        if current_search:

            lines.append("Current Search Context:")

            title = current_search.get("title", "")
            location = current_search.get("location", "")
            experience = current_search.get("experience", {})

            if title:
                lines.append(f"- Title: {title}")

            if location:
                lines.append(f"- Location: {location}")

            if experience:
                lines.append(
                    f"- Experience: {experience}"
                )

            required = current_search.get(
                "required_skills",
                [],
            )

            if required:

                skills = []

                for skill in required:

                    if isinstance(skill, dict):
                        skills.append(
                            skill.get("skill", "")
                        )
                    else:
                        skills.append(str(skill))

                lines.append(
                    f"- Required Skills: {', '.join(skills)}"
                )

        # --------------------------------------------------
        # Conversation History
        # --------------------------------------------------

        messages = conversation.get(
            "messages",
            [],
        )

        if messages:

            lines.append("")
            lines.append("Conversation History:")

            for message in messages:

                role = message.get(
                    "role",
                    "user",
                ).capitalize()

                content = message.get(
                    "content",
                    "",
                )

                lines.append(
                    f"{role}: {content}"
                )

        # --------------------------------------------------
        # Latest Search
        # --------------------------------------------------

        latest = conversation.get(
            "latest_search_id"
        )

        if latest:

            lines.append("")
            lines.append(
                f"Latest Search Id: {latest}"
            )

        summary = conversation.get(
            "context_summary",
            "",
        )

        if summary:

            lines.append("")
            lines.append(
                f"Summary: {summary}"
            )

        return "\n".join(lines)

    ###########################################################
    # Merge Parsed Job
    ###########################################################

    def merge_search(
        self,
        conversation: dict,
        parsed_search: dict,
    ):

        current_search = conversation.get(
            "current_search",
            {},
        )

        merged = self.context_merger.merge(
            current_search,
            parsed_search,
        )

        conversation["current_search"] = merged
        self.save(
            conversation["search_id"],
            conversation,
        )


        return merged

    ###########################################################
    # Add User Message
    ###########################################################

    def add_user_message(
        self,
        conversation: dict,
        message: str,
    ):

        conversation.setdefault(
            "messages",
            []
        ).append(
            {
                "role": "user",
                "content": message,
            }
        )
        self.save(
            conversation["search_id"],
            conversation,
        )
        return conversation

    ###########################################################
    # Add Assistant Message
    ###########################################################

    def add_assistant_message(
        self,
        conversation: dict,
        message,
        conversation_message_id: str = None,
    ):

        # Attach conversation message id only for search responses
        if (
            conversation_message_id
            and isinstance(message, dict)
            and message.get("type") in (
                "SEARCH",
                "SEARCH_MODIFICATION",
            )
        ):
            message["conversation_message_id"] = conversation_message_id

        conversation.setdefault(
            "messages",
            []
        ).append(
            {
                "role": "assistant",
                "content": message,
            }
        )

        self.save(
            conversation["search_id"],
            conversation,
        )

        return conversation

    ###########################################################
    # Latest Search
    ###########################################################

    def update_latest_search(
        self,
        conversation: dict,
        conversation_message_id: str,
    ):

        conversation["latest_search_id"] = conversation_message_id

        self.save(
            conversation["search_id"],
            conversation,
        )

        return conversation

    ###########################################################
    # Save Conversation
    ###########################################################

    def save(
        self,
        search_id: str,
        conversation: dict,
    ):

        self.search_repository.update_conversation(
            search_id,
            conversation,
        )