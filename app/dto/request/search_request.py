from typing import Optional
from pydantic import BaseModel


class SearchRequest(BaseModel):

    prompt: str

    search_id: Optional[str] = None

    job_position_id: Optional[str] = None

    received_within: Optional[str] = "ALL"

    global_search_allowed: bool = True