"""Main ADK pipeline orchestrator for pharma briefing generation."""

import asyncio
import json
import re
import time
from typing import Any

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.compliance_agent import compliance_agent
from agent.planner_agent import planner_agent
from agent.quality_gate_agent import claim_quality_gate
from agent.retriever_agent import retriever_agent
from agent.writer_agent import writer_agent
from tools.mongo_mcp_client import (
    MongoMcpRuntime,
    reset_active_mongodb_mcp,
    set_active_mongodb_mcp,
)
from tools.mongo_tools import save_briefing, update_meeting_status


APP_NAME = "pharma_briefing_agent"
USER_ID = "pipeline_user"
SESSION_ID_PREFIX = "pipeline_session"
PIPELINE_STEP_NAMES = [
    "MongoDBMCP",
    "MeetingPlanner",
    "InformationRetriever",
    "BriefWriter",
    "ClaimQualityGate",
    "ComplianceChecker",
    "ActionExecutor",
]


ACTION_EXECUTOR_INSTRUCTION = """You are the final action executor for the
pharma briefing pipeline. You receive compliance_result from
{compliance_result}.

Your job is to persist the final briefing and update the meeting status.

Step 1: Read compliance_result.
Step 2: Select the briefing to save:
- If compliance_result.passed is true, use compliance_result.clean_brief and
  set compliance_status to "passed".
- If compliance_result.passed is false, use compliance_result.clean_brief and
  set compliance_status to "needs_review".
Step 3: Ensure the briefing object includes:
- meeting_id
- hcp_id
- rep_id when available
- compliance_status
- compliance_loops set to 1
- drug_sections when present
- supporting_evidence when present
- evidence_ledger when present
- quality_gate_status when present
- cross_drug_notes when present
- rep_workflow_notes when present, including objective, sample reminders, and
  follow-up reminders
- rep_summary_report: A friendly, cohesive narrative note (2-3 paragraphs) written directly to the sales rep summarizing the meeting strategy, clinical highlights, objection handling, and sample/follow-up reminders, using the information from the brief.
- draft_email_subject
- draft_email_body
- flags copied from compliance_result.flags
Step 4: Call save_briefing with briefing_data as a JSON string.
Step 5: Call update_meeting_status with:
- meeting_id from the briefing
- status "briefing_ready" if compliance passed, otherwise "needs_review"
- briefing_id from save_briefing.briefing_id

Output ONLY one valid JSON object. The first character must be "{" and the last
character must be "}". Do not use Markdown fences or explanatory text.

Return this structure:
{
  "status": "saved",
  "passed": true,
  "meeting_id": "...",
  "briefing_id": "...",
  "meeting_update": {},
  "final_briefing": {}
}

If save_briefing or update_meeting_status returns an error, preserve that tool
response in the output and set status to "error". Do not hide tool failures.
Output ONLY valid JSON with no trailing commas."""


def _strip_json_markdown_fence(callback_context, llm_response):
    """Normalize final model text when Gemini wraps JSON in Markdown fences."""
    del callback_context

    content = llm_response.content
    if not content or not content.parts:
        return None

    for part in content.parts:
        if not part.text:
            continue

        text = part.text.strip()
        match = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if match:
            part.text = match.group(1).strip()

    return llm_response


action_executor = LlmAgent(
    name="ActionExecutor",
    model="gemini-3.1-flash-lite",
    tools=[save_briefing, update_meeting_status],
    output_key="final_briefing",
    instruction=ACTION_EXECUTOR_INSTRUCTION,
    after_model_callback=_strip_json_markdown_fence,
)


pipeline = SequentialAgent(
    name="PharmaBriefingPipeline",
    sub_agents=[
        planner_agent,
        retriever_agent,
        writer_agent,
        claim_quality_gate,
        compliance_agent,
        action_executor,
    ],
)


def _parse_json_if_possible(value: Any) -> Any:
    """Return decoded JSON when ADK state stores an agent output as text."""
    if not isinstance(value, str):
        return value

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


async def _run_pipeline_async(meeting_id: str) -> Any:
    result = await _run_pipeline_with_metadata_async(meeting_id)
    return result["final_briefing"]


def _emit_trace(trace_callback, payload: dict[str, Any]) -> None:
    if not trace_callback:
        return
    try:
        trace_callback(payload)
    except Exception:
        return


async def _run_pipeline_with_metadata_async(meeting_id: str, trace_callback=None) -> dict[str, Any]:
    async with MongoMcpRuntime(trace_callback=trace_callback) as mongo_mcp:
        token = set_active_mongodb_mcp(mongo_mcp)
        try:
            return await _run_adk_pipeline_with_metadata_async(meeting_id, trace_callback=trace_callback)
        finally:
            reset_active_mongodb_mcp(token)


async def _run_adk_pipeline_with_metadata_async(meeting_id: str, trace_callback=None) -> dict[str, Any]:
    session_service = InMemorySessionService()
    session_id = f"{SESSION_ID_PREFIX}_{meeting_id}"

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )

    runner = Runner(
        app_name=APP_NAME,
        agent=pipeline,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=f"meeting_id: {meeting_id}")],
    )

    final_response_text = None
    pipeline_started = time.perf_counter()
    step_timings: dict[str, dict[str, Any]] = {}
    active_step: str | None = None

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=message,
    ):
        event_time = time.perf_counter()
        author = getattr(event, "author", None)
        if author in PIPELINE_STEP_NAMES:
            if active_step != author:
                if active_step:
                    _emit_trace(
                        trace_callback,
                        {
                            "step": active_step,
                            "phase": "completed",
                        },
                    )
                active_step = author
                _emit_trace(
                    trace_callback,
                    {
                        "step": author,
                        "phase": "started",
                    },
                )

            step_timing = step_timings.setdefault(
                author,
                {
                    "started_at_offset_ms": round(
                        (event_time - pipeline_started) * 1000, 2
                    ),
                    "event_count": 0,
                },
            )
            step_timing["event_count"] += 1
            step_timing["_last_seen"] = event_time

        if not event.is_final_response() or not event.content:
            continue

        for part in event.content.parts or []:
            if part.text:
                final_response_text = part.text

    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )

    if session and "final_briefing" in session.state:
        final_briefing = _parse_json_if_possible(session.state["final_briefing"])
    else:
        final_briefing = _parse_json_if_possible(final_response_text)

    pipeline_finished = time.perf_counter()
    if active_step:
        _emit_trace(
            trace_callback,
            {
                "step": active_step,
                "phase": "completed",
            },
        )

    for step_name in PIPELINE_STEP_NAMES:
        if step_name not in step_timings:
            step_timings[step_name] = {
                "started_at_offset_ms": None,
                "duration_ms": None,
                "event_count": 0,
            }
            continue

        last_seen = step_timings[step_name].pop("_last_seen")
        first_seen = pipeline_started + (
            step_timings[step_name]["started_at_offset_ms"] / 1000
        )
        step_timings[step_name]["duration_ms"] = round((last_seen - first_seen) * 1000, 2)

    return {
        "final_briefing": final_briefing,
        "timings": {
            "total_ms": round((pipeline_finished - pipeline_started) * 1000, 2),
            "per_step": step_timings,
        },
    }


def run_pipeline(meeting_id: str) -> Any:
    """Run the full briefing pipeline for a meeting_id and return final output."""
    return asyncio.run(_run_pipeline_async(meeting_id))


def run_pipeline_with_metadata(meeting_id: str, trace_callback=None) -> dict[str, Any]:
    """Run the full briefing pipeline and return final output plus timings."""
    return asyncio.run(_run_pipeline_with_metadata_async(meeting_id, trace_callback=trace_callback))


if __name__ == "__main__":
    result = run_pipeline("mtg_001")
    print(json.dumps(result, indent=2, ensure_ascii=False))
