import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from services import agent_runner
from services.meeting_service import get_meeting_detail, request_briefing_generation

logger = logging.getLogger("pharmaops.briefings_router")

router = APIRouter()


@router.get("/{meeting_id}")
async def get_meeting_briefing(meeting_id: str) -> dict:
    """Return meeting detail including briefing if available.

    This endpoint is a pure DB read — it should NEVER call the Gemini model.
    Errors here are exclusively database or serialization issues.
    """
    logger.info("[GET /%s] Fetching meeting detail (DB-only, no model calls)", meeting_id)

    try:
        meeting = await get_meeting_detail(meeting_id)
    except Exception as exc:
        logger.error("[GET /%s] Unexpected error in get_meeting_detail: %s", meeting_id, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"Failed to load meeting detail: {exc}",
            },
        )

    if not meeting:
        logger.warning("[GET /%s] Meeting not found", meeting_id)
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MEETING_NOT_FOUND",
                "message": f"No meeting found with ID {meeting_id}",
            },
        )

    logger.info(
        "[GET /%s] Returning: status=%s, has_briefing=%s",
        meeting_id,
        meeting.get("status"),
        meeting.get("briefing") is not None,
    )
    return meeting


@router.post("/{meeting_id}/briefing/generate")
async def generate_meeting_briefing(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(False),
) -> dict:
    logger.info(
        "[POST /%s/briefing/generate] force=%s",
        meeting_id,
        force,
    )

    try:
        meeting, should_start = await request_briefing_generation(meeting_id, force=force)
    except Exception as exc:
        logger.error(
            "[POST /%s/briefing/generate] Error in request_briefing_generation: %s",
            meeting_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "GENERATION_ERROR",
                "message": f"Failed to start briefing generation: {exc}",
            },
        )

    if not meeting:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MEETING_NOT_FOUND",
                "message": f"No meeting found with ID {meeting_id}",
            },
        )

    if should_start:
        logger.info("[POST /%s/briefing/generate] Scheduling agent run in background", meeting_id)
        background_tasks.add_task(agent_runner.run, meeting_id)
    else:
        logger.info(
            "[POST /%s/briefing/generate] No new generation needed (briefing exists or already processing)",
            meeting_id,
        )

    return {
        **meeting,
        "generation_started": should_start,
    }
