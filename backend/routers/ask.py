from fastapi import APIRouter, HTTPException

from models.ask import AskRequest, AskResponse
from services.ask_service import answer_question


router = APIRouter()


@router.post("", response_model=AskResponse)
@router.post("/", response_model=AskResponse)
async def ask(payload: AskRequest) -> dict:
    response = await answer_question(payload.meeting_id, payload.question)
    if not response:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MEETING_NOT_FOUND",
                "message": f"No meeting found with ID {payload.meeting_id}",
            },
        )
    return response

