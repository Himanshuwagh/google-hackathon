from pydantic import BaseModel


class AskRequest(BaseModel):
    meeting_id: str
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]
    meeting_id: str

