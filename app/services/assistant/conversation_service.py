from copy import deepcopy

from app.repository.job_repository import JobRepository
from app.utils.context_merger import ContextMerger


class ConversationService:

    def __init__(self):
        self.job_repository = JobRepository()
        self.context_merger = ContextMerger()

    ###########################################################
    # Load Conversation
    ###########################################################

    def load(
        self,
        job_id: str,
    ):

        if not job_id:
            return None

        conversation = self.job_repository.get_conversation(
            job_id
        )

        if not conversation:
            return self.create()

        conversation["job_id"] = job_id

        return conversation

    ###########################################################
    # Create Empty Conversation
    ###########################################################

    def create(
        self,
    ):

        job_id = self.job_repository.create_empty_job()

        conversation = {

            "job_id": job_id,

            "messages": [],

            "current_job": {},

            "latest_search_id": None,

            "context_summary": "",

        }

        self.save(

            job_id,

            conversation,

        )

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

        current_job = conversation.get("current_job", {})

        if current_job:

            lines.append("Current Search Context:")

            title = current_job.get("title", "")
            location = current_job.get("location", "")
            experience = current_job.get("experience", {})

            if title:
                lines.append(f"- Title: {title}")

            if location:
                lines.append(f"- Location: {location}")

            if experience:
                lines.append(
                    f"- Experience: {experience}"
                )

            required = current_job.get(
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

    def merge_job(
        self,
        conversation: dict,
        parsed_job: dict,
    ):

        current_job = conversation.get(
            "current_job",
            {},
        )

        merged = self.context_merger.merge(
            current_job,
            parsed_job,
        )

        conversation["current_job"] = merged
        self.save(
            conversation["job_id"],
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
            conversation["job_id"],
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
    ):

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
            conversation["job_id"],
            conversation,
        )


        return conversation

    ###########################################################
    # Latest Search
    ###########################################################

    def update_latest_search(
        self,
        conversation: dict,
        job_id: str,
    ):

        conversation["latest_search_id"] = job_id
        self.save(
            conversation["job_id"],
            conversation,
        )


        return conversation

    ###########################################################
    # Save Conversation
    ###########################################################

    def save(
        self,
        job_id: str,
        conversation: dict,
    ):

        self.job_repository.update_conversation(
            job_id,
            conversation,
        )