"""MongoDB change stream listener for scheduled meeting briefing runs."""

from __future__ import annotations

import signal
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from agent.main_agent import run_pipeline_with_metadata
from config import MONGO_DB_NAME, MONGO_URI


SHUTDOWN = threading.Event()


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for MongoDB run logs."""
    return datetime.now(timezone.utc)


def log(message: str) -> None:
    """Print a timestamped trigger log line."""
    print(f"[{utc_now().isoformat()}] {message}", flush=True)


def handle_shutdown(signum: int, _frame: Any) -> None:
    """Handle SIGINT/SIGTERM by letting the watch loop exit cleanly."""
    log(f"Received signal {signum}; shutting down gracefully...")
    SHUTDOWN.set()


def claim_meeting(meetings: Collection, meeting_id: str) -> bool:
    """Atomically mark a scheduled meeting as triggered before processing."""
    result = meetings.update_one(
        {
            "_id": meeting_id,
            "status": "scheduled",
            "agent_triggered": False,
        },
        {
            "$set": {
                "agent_triggered": True,
                "agent_triggered_at": utc_now(),
                "status": "processing",
            }
        },
    )
    return result.modified_count == 1


def log_agent_run(
    agent_runs: Collection,
    meeting_id: str,
    status: str,
    started_at: datetime,
    result: Any | None = None,
    timings: dict[str, Any] | None = None,
    error: str | None = None,
    traceback_text: str | None = None,
) -> None:
    """Persist the outcome of a pipeline attempt to agent_runs."""
    finished_at = utc_now()
    run_doc = {
        "meeting_id": meeting_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": round((finished_at - started_at).total_seconds() * 1000, 2),
        "timings": timings or {},
        "result": result,
        "error": error,
        "traceback": traceback_text,
    }
    agent_runs.insert_one(run_doc)


def should_trigger(document: dict[str, Any]) -> bool:
    """Return true when a meeting document should start the pipeline."""
    return (
        document.get("status") == "scheduled"
        and document.get("agent_triggered") is False
        and document.get("_id") is not None
    )


def process_meeting(
    meetings: Collection,
    agent_runs: Collection,
    meeting_doc: dict[str, Any],
) -> None:
    """Claim a meeting, run the pipeline, and log success or failure."""
    meeting_id = str(meeting_doc["_id"])

    if not claim_meeting(meetings, meeting_id):
        log(f"Skipped {meeting_id}; it was already claimed or no longer scheduled.")
        return

    log(f"Triggered pipeline for {meeting_id}...")
    started_at = utc_now()

    try:
        run_result = run_pipeline_with_metadata(meeting_id)
        final_briefing = run_result.get("final_briefing")
        timings = run_result.get("timings", {})

        log_agent_run(
            agent_runs=agent_runs,
            meeting_id=meeting_id,
            status="success",
            started_at=started_at,
            result=final_briefing,
            timings=timings,
        )

        total_ms = timings.get("total_ms", "unknown")
        log(f"Pipeline completed for {meeting_id} in {total_ms} ms.")

    except Exception as exc:  # Keep the watcher alive after pipeline failures.
        error_text = str(exc)
        traceback_text = traceback.format_exc()
        log(f"Pipeline failed for {meeting_id}: {error_text}")

        try:
            meetings.update_one(
                {"_id": meeting_id},
                {
                    "$set": {
                        "status": "agent_error",
                        "agent_error": error_text,
                        "agent_error_at": utc_now(),
                    }
                },
            )
        except PyMongoError as mongo_exc:
            log(f"Failed to mark {meeting_id} as agent_error: {mongo_exc}")

        try:
            log_agent_run(
                agent_runs=agent_runs,
                meeting_id=meeting_id,
                status="error",
                started_at=started_at,
                error=error_text,
                traceback_text=traceback_text,
            )
        except PyMongoError as mongo_exc:
            log(f"Failed to write agent_runs error log for {meeting_id}: {mongo_exc}")


def watch_meetings() -> None:
    """Watch MongoDB for scheduled meetings and trigger briefing generation."""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    meetings = db["meetings"]
    agent_runs = db["agent_runs"]

    watch_pipeline = [
        {
            "$match": {
                "operationType": {"$in": ["insert", "replace", "update"]},
            }
        }
    ]

    log("Watching for new meetings...")

    while not SHUTDOWN.is_set():
        try:
            with meetings.watch(
                watch_pipeline,
                full_document="updateLookup",
                max_await_time_ms=1000,
            ) as stream:
                for change in stream:
                    if SHUTDOWN.is_set():
                        break

                    meeting_doc = change.get("fullDocument") or {}
                    if not should_trigger(meeting_doc):
                        continue

                    process_meeting(meetings, agent_runs, meeting_doc)

        except KeyboardInterrupt:
            handle_shutdown(signal.SIGINT, None)
        except PyMongoError as exc:
            if SHUTDOWN.is_set():
                break

            log(f"Change stream error: {exc}; retrying in 5 seconds...")
            time.sleep(5)

    client.close()
    log("Meeting watcher stopped.")


def main() -> None:
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    watch_meetings()


if __name__ == "__main__":
    main()
