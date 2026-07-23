from typing import Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    # Existing conversation
    job_id: Optional[str] = None

    # Keeping this for compatibility
    job_position: str = "all"

    # User message (search / refinement / general question)
    prompt: str

    received_within: str = "ALL"