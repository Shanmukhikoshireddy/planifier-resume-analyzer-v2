from pydantic import BaseModel
from typing import Optional

class RejectRequest(BaseModel):
    search_result_id: str
    recruiter: str = "Recruiter"
    reason: str | None = None