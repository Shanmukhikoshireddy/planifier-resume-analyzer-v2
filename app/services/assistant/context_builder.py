from typing import List, Dict


class ContextBuilder:

    def build(
        self,
        job: Dict | None = None,
        candidates: List[Dict] | None = None,
    ) -> str:

        context = """
You are an AI Recruitment Assistant.

You answer recruiter questions using only the provided context.

Rules:
- Do not make up information.
- If the answer is unavailable, clearly say so.
- Be concise and professional.
"""

        return context.strip()