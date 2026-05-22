import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from log_store import get_log_history, is_complete, subscribe, unsubscribe
from services.meeting_service import get_meeting_detail


router = APIRouter()


@router.websocket("/log/{meeting_id}")
async def stream_logs(websocket: WebSocket, meeting_id: str) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()

    try:
        meeting = await get_meeting_detail(meeting_id)
        if not meeting:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "MEETING_NOT_FOUND",
                    "message": f"No meeting found with ID {meeting_id}",
                }
            )
            await websocket.close(code=1008)
            return

        for line in get_log_history(meeting_id):
            await websocket.send_json(line)

        if is_complete(meeting_id) or meeting.get("status") in {"briefing_ready", "failed"}:
            await websocket.send_json({"type": "complete"})
            await websocket.close()
            return

        if meeting.get("status") == "scheduled":
            await websocket.send_json({"type": "waiting"})

        subscribe(meeting_id, queue)
        while True:
            line = await queue.get()
            await websocket.send_json(line)
            if line.get("type") == "complete":
                await websocket.close()
                return
    except WebSocketDisconnect:
        return
    finally:
        unsubscribe(meeting_id, queue)

