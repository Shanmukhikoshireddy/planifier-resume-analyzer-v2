from app.services.assistant.context_builder import ContextBuilder
from app.services.shared.openai_service import OpenAIService
from app.services.orchestrator.prompt_parser_service import PromptParserService
from app.services.search.search_service import SearchService


class AssistantService:

    def __init__(self):

        self.prompt_parser = PromptParserService()
        self.search_service = SearchService()
        self.context_builder = ContextBuilder()
        self.openai_service = OpenAIService()

    def process(
        self,
        request,
        page: int,
        page_size: int,
    ):

        parsed = self.prompt_parser.parse(
            request.job_description
        )

        intent = parsed["intent"]

        if intent == "SEARCH":

            return self.search_service.search(
                job_position=request.job_position,
                job_description=request.job_description,
                received_within=request.received_within,
                page=page,
                page_size=page_size,
            )

        return self.answer_general(
            request.job_description
        )

    def answer_general(
        self,
        question: str,
    ):

        context = self.context_builder.build()

        messages = [
            {
                "role": "system",
                "content": context,
            },
            {
                "role": "user",
                "content": question,
            },
        ]

        answer = self.openai_service.generate(messages)

        return {
            "type": "GENERAL",
            "answer": answer,
        }