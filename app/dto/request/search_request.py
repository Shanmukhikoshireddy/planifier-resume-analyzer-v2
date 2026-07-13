from pydantic import BaseModel

class SearchRequest(BaseModel):
    job_position: str
    job_description: str
    received_within: str = "ALL"
