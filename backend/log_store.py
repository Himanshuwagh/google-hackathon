import datetime
from asyncio import Queue
from collections import defaultdict
from typing import Any


log_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
log_subscribers: dict[str, list[Queue]] = defaultdict(list)
completed_meetings: set[str] = set()


def append_log(
    meeting_id: str,
    tag: str,
    message: str,
    level: str = "info",
    **extra: Any,
) -> None:
    line = {
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "tag": tag,
        "message": message,
        "level": level,
        **extra,
    }
    log_history[meeting_id].append(line)
    for queue in list(log_subscribers[meeting_id]):
        queue.put_nowait(line)


def mark_complete(meeting_id: str) -> None:
    completed_meetings.add(meeting_id)
    for queue in list(log_subscribers[meeting_id]):
        queue.put_nowait({"type": "complete"})


def is_complete(meeting_id: str) -> bool:
    return meeting_id in completed_meetings


def get_log_history(meeting_id: str) -> list[dict[str, Any]]:
    return log_history.get(meeting_id, [])


def subscribe(meeting_id: str, queue: Queue) -> None:
    log_subscribers[meeting_id].append(queue)


def unsubscribe(meeting_id: str, queue: Queue) -> None:
    subscribers = log_subscribers.get(meeting_id, [])
    if queue in subscribers:
        subscribers.remove(queue)
