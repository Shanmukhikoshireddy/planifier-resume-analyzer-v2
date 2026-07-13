from pydantic import BaseModel
from typing import Optional

class ShortlistRequest(BaseModel):
    search_result_id: str
    recruiter: str = "Recruiter"