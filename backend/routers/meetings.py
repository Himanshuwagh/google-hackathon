from fastapi import APIRouter, BackgroundTasks, Query

from models.meeting import MeetingListItem, NewMeetingRequest, NewMeetingResponse
from services import agent_runner
from services.meeting_service import create_meeting, get_meeting_form_options, list_meetings


router = APIRouter()
singular_router = APIRouter()


@router.get("/options")
async def get_meeting_options(rep_id: str = Query(...)) -> dict:
    return await get_meeting_form_options(rep_id)


@router.get("", response_model=list[MeetingListItem])
@router.get("/", response_model=list[MeetingListItem])
async def get_meetings(
    rep_id: str = Query(...),
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    start_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> list[dict]:
    return await list_meetings(
        rep_id=rep_id,
        date=date,
        start_date=start_date,
        end_date=end_date,
    )


async def _create_meeting_response(
    payload: NewMeetingRequest,
    background_tasks: BackgroundTasks,
) -> NewMeetingResponse:
    meeting_id = await create_meeting(payload)
    background_tasks.add_task(agent_runner.run, meeting_id)
    return NewMeetingResponse(
        meeting_id=meeting_id,
        status="scheduled",
        message="Meeting added. Agent will prepare your briefing shortly.",
    )


@router.post("", response_model=NewMeetingResponse, status_code=201)
@router.post("/", response_model=NewMeetingResponse, status_code=201)
async def post_meeting_plural(
    payload: NewMeetingRequest,
    background_tasks: BackgroundTasks,
) -> NewMeetingResponse:
    return await _create_meeting_response(payload, background_tasks)


@singular_router.post("", response_model=NewMeetingResponse, status_code=201)
@singular_router.post("/", response_model=NewMeetingResponse, status_code=201)
async def post_meeting_singular(
    payload: NewMeetingRequest,
    background_tasks: BackgroundTasks,
) -> NewMeetingResponse:
    return await _create_meeting_response(payload, background_tasks)
