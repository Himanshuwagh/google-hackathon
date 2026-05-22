import asyncio
import logging
from functools import partial
import sys
from datetime import UTC, datetime
from typing import Any

from starlette.concurrency import run_in_threadpool

from db import get_database
from log_store import append_log, mark_complete
from runtime_config import AGENT_ROOT, configure_environment
from services.meeting_service import update_meeting_status

logger = logging.getLogger("pharmaops.agent_runner")

PIPELINE_STEP_NAMES = [
    "MeetingPlanner",
    "InformationRetriever",
    "BriefWriter",
    "ClaimQualityGate",
    "ComplianceChecker",
    "ActionExecutor",
]


def _prepare_agent_environment() -> None:
    configure_environment()


def _import_agent_run_pipeline():
    _prepare_agent_environment()
    agent_root = str(AGENT_ROOT)
    if agent_root not in sys.path:
        sys.path.insert(0, agent_root)
    from agent.main_agent import run_pipeline_with_metadata

    return run_pipeline_with_metadata


def _extract_briefing_id(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    if isinstance(result.get("final_briefing"), dict):
        return _extract_briefing_id(result["final_briefing"])
    return result.get("briefing_id") or result.get("meeting_update", {}).get("briefing_id")


async def _record_agent_run(
    meeting_id: str,
    status: str,
    started_at: datetime,
    result: Any | None = None,
    error: str | None = None,
) -> None:
    db = get_database()
    await db["agent_runs"].insert_one(
        {
            "meeting_id": meeting_id,
            "status": status,
            "started_at": started_at,
            "finished_at": datetime.now(UTC),
            "result": result,
            "error": error,
        }
    )


def _new_trace_event(tag: str, message: str, level: str = "info", **extra: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "timestamp": now.strftime("%H:%M:%S"),
        "recorded_at": now.isoformat(),
        "tag": tag,
        "message": message,
        "level": level,
        **extra,
    }


def _build_tool_trace(status: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    steps = {
        step_name: {
            "status": "waiting",
            "started_at": None,
            "completed_at": None,
        }
        for step_name in PIPELINE_STEP_NAMES
    }

    for event in events:
        if event.get("tag") != "STEP":
            continue

        step = event.get("step")
        phase = event.get("phase")
        if step not in steps:
            continue

        if phase == "started":
            steps[step]["status"] = "running"
            steps[step]["started_at"] = event.get("recorded_at")
        elif phase == "completed":
            steps[step]["status"] = "done"
            steps[step]["completed_at"] = event.get("recorded_at")

    if status == "error":
        for step in steps.values():
            if step["status"] == "running":
                step["status"] = "failed"

    if status == "complete":
        for step in steps.values():
            if step["status"] in {"waiting", "running"}:
                step["status"] = "done"

    return {
        "status": status,
        "events": events,
        "steps": steps,
    }


async def _persist_tool_trace(
    meeting_id: str,
    briefing_id: str,
    tool_trace: dict[str, Any],
) -> None:
    db = get_database()
    await db["briefings"].update_one(
        {
            "$or": [
                {"_id": briefing_id},
                {"briefing_id": briefing_id},
                {"meeting_id": meeting_id},
            ]
        },
        {"$set": {"tool_trace": tool_trace}},
    )


async def run(meeting_id: str) -> None:
    logger.info("[RUN] Starting agent pipeline for meeting_id=%s", meeting_id)
    started_at = datetime.now(UTC)
    loop = asyncio.get_running_loop()
    trace_events: list[dict[str, Any]] = []

    def emit_step_trace(payload: dict[str, Any]) -> None:
        step = payload.get("step")
        phase = payload.get("phase")
        if not step or not phase:
            return

        action = "started" if phase == "started" else "completed"
        level = "success" if phase == "completed" else "info"
        logger.info("[RUN] Step trace: %s %s", step, action)
        trace_events.append(
            _new_trace_event(
                "STEP",
                f"{step} {action}",
                level,
                step=step,
                phase=phase,
            )
        )
        loop.call_soon_threadsafe(
            partial(
                append_log,
                meeting_id,
                "STEP",
                f"{step} {action}",
                level,
                step=step,
                phase=phase,
            )
        )

    append_log(meeting_id, "TRIGGER", f"Meeting detected - {meeting_id}")
    await update_meeting_status(
        meeting_id,
        "agent_processing",
        agent_triggered=True,
    )

    try:
        append_log(meeting_id, "AGENT", "Starting briefing pipeline")
        logger.info("[RUN] Importing agent pipeline module")

        run_pipeline_with_metadata = _import_agent_run_pipeline()
        logger.info("[RUN] Running pipeline in threadpool")
        result = await run_in_threadpool(
            run_pipeline_with_metadata,
            meeting_id,
            trace_callback=emit_step_trace,
        )

        briefing_id = _extract_briefing_id(result)
        logger.info("[RUN] Pipeline completed. briefing_id=%s", briefing_id)

        if briefing_id:
            await update_meeting_status(meeting_id, "briefing_ready", briefing_id=briefing_id)
            logger.info("[RUN] Meeting status updated to briefing_ready")
        else:
            logger.warning("[RUN] No briefing_id extracted from pipeline result")

        await _record_agent_run(meeting_id, "success", started_at, result=result)
        trace_events.append(_new_trace_event("DONE", "Briefing ready", level="success"))
        if briefing_id:
            await _persist_tool_trace(
                meeting_id,
                briefing_id,
                _build_tool_trace("complete", trace_events),
            )
        append_log(meeting_id, "DONE", "Briefing ready", level="success")
        logger.info("[RUN] Agent run complete for meeting_id=%s", meeting_id)
    except Exception as exc:
        error_text = str(exc)
        logger.error(
            "[RUN] Pipeline failed for meeting_id=%s: %s", meeting_id, error_text, exc_info=True
        )
        await update_meeting_status(
            meeting_id,
            "failed",
            error_message=error_text,
            agent_triggered=True,
        )
        await _record_agent_run(meeting_id, "error", started_at, error=error_text)
        trace_events.append(_new_trace_event("ERROR", error_text, level="error"))
        append_log(meeting_id, "ERROR", error_text, level="error")
    finally:
        mark_complete(meeting_id)


def schedule(meeting_id: str) -> None:
    asyncio.create_task(run(meeting_id))
