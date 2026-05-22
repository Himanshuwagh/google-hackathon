"""Interactive CLI demo for the pharma AI briefing agent pipeline."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pymongo import MongoClient
from pymongo.database import Database

from agent.main_agent import APP_NAME, USER_ID, pipeline
from config import MONGO_DB_NAME, MONGO_URI


STEP_LABELS = {
    "MeetingPlanner": ("Step 1", "Planning"),
    "InformationRetriever": ("Step 2", "Retrieving from 3 sources"),
    "BriefWriter": ("Step 3", "Writing brief"),
    "ComplianceChecker": ("Step 4", "Compliance check"),
    "ActionExecutor": ("Step 5", "Actions"),
}


class Theme:
    def __init__(self) -> None:
        enabled = sys.stdout.isatty()
        self.reset = "\033[0m" if enabled else ""
        self.bold = "\033[1m" if enabled else ""
        self.dim = "\033[2m" if enabled else ""
        self.green = "\033[32m" if enabled else ""
        self.yellow = "\033[33m" if enabled else ""
        self.red = "\033[31m" if enabled else ""
        self.cyan = "\033[36m" if enabled else ""


THEME = Theme()


def parse_json_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def elapsed_text(started_at: float) -> str:
    return f"{time.perf_counter() - started_at:.1f}s"


class StepPrinter:
    def __init__(self) -> None:
        self.current_author: str | None = None
        self.current_started_at: float | None = None

    def start(self, author: str) -> None:
        if author == self.current_author:
            return

        self.finish()
        step, label = STEP_LABELS[author]
        print(f"{THEME.cyan}{step}:{THEME.reset} {label}... ", end="", flush=True)
        self.current_author = author
        self.current_started_at = time.perf_counter()

    def finish(self, detail: str | None = None, failed: bool = False) -> None:
        if not self.current_author or self.current_started_at is None:
            return

        marker = "x" if failed else "✓"
        color = THEME.red if failed else THEME.green
        extra = f" {detail}" if detail else ""
        print(f"{color}{marker}{THEME.reset}{extra} ({elapsed_text(self.current_started_at)})")
        self.current_author = None
        self.current_started_at = None


def print_banner() -> None:
    print(f"{THEME.bold}=== Pharma AI Briefing Agent Demo ==={THEME.reset}")
    print(f"{THEME.dim}MongoDB: {MONGO_DB_NAME}{THEME.reset}\n")


def connect_db() -> tuple[MongoClient, Database]:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client, client[MONGO_DB_NAME]


def get_name(db: Database, collection: str, item_id: str, fallback: str) -> str:
    doc = db[collection].find_one({"_id": item_id}) or {}
    return doc.get("name") or doc.get("brand_name") or fallback


def normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def list_sales_reps(db: Database) -> list[dict[str, Any]]:
    reps = list(db["sales_reps"].find({}).sort("name", 1))

    print(f"{THEME.bold}Sales Rep Login{THEME.reset}")
    print("-" * 92)
    print(f"{'#':<3} {'rep_id':<24} {'name':<22} {'territory':<18} {'email'}")
    print("-" * 92)
    for index, rep in enumerate(reps, start=1):
        print(
            f"{index:<3} {rep.get('_id', ''):<24} {rep.get('name', '')[:21]:<22} "
            f"{rep.get('territory', '')[:17]:<18} {rep.get('email', '')}"
        )
    print()
    return reps


def resolve_rep_choice(reps: list[dict[str, Any]], choice: str) -> dict[str, Any] | None:
    if not reps:
        return None

    if not choice:
        return reps[0]

    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(reps):
            return reps[index - 1]

    normalized_choice = normalize_text(choice)
    for rep in reps:
        candidates = [
            rep.get("_id", ""),
            rep.get("name", ""),
            rep.get("email", ""),
        ]
        if normalized_choice in {normalize_text(candidate) for candidate in candidates}:
            return rep

    partial_matches = [
        rep
        for rep in reps
        if normalized_choice
        and normalized_choice in normalize_text(rep.get("name", ""))
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]

    return None


def login_sales_rep(db: Database) -> dict[str, Any]:
    reps = list_sales_reps(db)
    if not reps:
        raise RuntimeError("No sales reps found in MongoDB.")

    while True:
        choice = input("Login as sales rep name/id/email, or press Enter for first: ").strip()
        rep = resolve_rep_choice(reps, choice)
        if rep:
            print(
                f"\n{THEME.green}Logged in:{THEME.reset} "
                f"{rep.get('name')} ({rep.get('_id')}) - {rep.get('territory')}\n"
            )
            return rep

        print(f"{THEME.yellow}No matching rep found. Try name, email, id, or list number.{THEME.reset}")


def meeting_drug_ids(meeting: dict[str, Any]) -> list[str]:
    drug_ids = meeting.get("drug_ids")
    if isinstance(drug_ids, list):
        normalized = [drug_id for drug_id in drug_ids if isinstance(drug_id, str)]
    elif isinstance(drug_ids, str):
        normalized = [drug_ids]
    else:
        normalized = []

    legacy_drug_id = meeting.get("drug_id")
    if not normalized and isinstance(legacy_drug_id, str):
        normalized = [legacy_drug_id]

    detailing_sequence = meeting.get("detailing_sequence")
    if isinstance(detailing_sequence, list):
        sequence = [drug_id for drug_id in detailing_sequence if drug_id in normalized]
        remaining = [drug_id for drug_id in normalized if drug_id not in sequence]
        normalized = sequence + remaining

    return normalized


def meeting_drug_names(db: Database, meeting: dict[str, Any]) -> str:
    names = [
        get_name(db, "drugs", drug_id, drug_id)
        for drug_id in meeting_drug_ids(meeting)
    ]
    if not names:
        return "Unknown drug"
    return " + ".join(names)


def list_scheduled_meetings(db: Database, rep: dict[str, Any]) -> list[dict[str, Any]]:
    rep_id = rep["_id"]
    meetings = list(
        db["meetings"]
        .find({"status": "scheduled", "rep_id": rep_id})
        .sort("meeting_date", 1)
    )

    print(f"{THEME.bold}Upcoming Meetings for {rep.get('name')}{THEME.reset}")
    if not meetings:
        print(f"{THEME.yellow}No scheduled meetings found for this rep.{THEME.reset}\n")
        return []

    print("-" * 92)
    print(f"{'#':<3} {'meeting_id':<20} {'doctor':<22} {'drugs':<30} {'duration':<9} {'date'}")
    print("-" * 92)
    for index, meeting in enumerate(meetings, start=1):
        hcp_name = get_name(db, "hcp_profiles", meeting.get("hcp_id"), "Unknown HCP")
        drug_name = meeting_drug_names(db, meeting)
        print(
            f"{index:<3} {meeting['_id']:<20} {hcp_name[:21]:<22} "
            f"{drug_name[:29]:<30} {str(meeting.get('duration_mins', '')) + ' mins':<9} "
            f"{meeting.get('meeting_date', '')}"
        )
    print()
    return meetings


def create_fresh_meeting(db: Database, rep: dict[str, Any]) -> str:
    template = db["meetings"].find_one({"rep_id": rep["_id"]}) or {
        "rep_id": rep["_id"],
        "hcp_id": "hcp_ananya_mehta",
        "location": "Demo Clinic",
        "duration_mins": 20,
    }

    meeting_id = f"mtg_demo_multi_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    meeting = {
        **template,
        "_id": meeting_id,
        "rep_id": rep["_id"],
        "drug_ids": ["drug_lisinopril_10mg", "drug_amlodipine_5mg"],
        "detailing_sequence": ["drug_lisinopril_10mg", "drug_amlodipine_5mg"],
        "objective": "Address cost concerns and position hypertension portfolio for mixed cardiac patients",
        "planned_samples": [
            {
                "drug_id": "drug_lisinopril_10mg",
                "quantity": 10,
            }
        ],
        "pending_action_items": [
            "Provide renal safety data for diabetic hypertensive patients",
            "Clarify patient assistance program eligibility",
        ],
        "meeting_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "status": "scheduled",
        "agent_triggered": False,
        "briefing_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    meeting.pop("drug_id", None)
    db["meetings"].insert_one(meeting)
    print(f"{THEME.green}Created fresh multi-drug demo meeting:{THEME.reset} {meeting_id}\n")
    return meeting_id


def print_meeting_preview(db: Database, meeting: dict[str, Any]) -> None:
    hcp_name = get_name(db, "hcp_profiles", meeting.get("hcp_id"), "Unknown HCP")
    drug_names = meeting_drug_names(db, meeting)
    sample_count = sum(
        int(sample.get("quantity", 0))
        for sample in meeting.get("planned_samples", [])
        if isinstance(sample, dict)
    )

    print(f"{THEME.bold}Meeting Preview{THEME.reset}")
    print("-" * 92)
    print(f"Meeting ID: {meeting.get('_id')}")
    print(f"Doctor:     {hcp_name}")
    print(f"When:       {meeting.get('meeting_date')}")
    print(f"Location:   {meeting.get('location')}")
    print(f"Duration:   {meeting.get('duration_mins')} mins")
    print(f"Drugs:      {drug_names}")
    print(f"Objective:  {meeting.get('objective')}")
    print(f"Samples:    {sample_count if sample_count else 'none planned'}")
    action_items = meeting.get("pending_action_items") or []
    if action_items:
        print("Follow-ups:")
        for item in action_items:
            print(f"  - {item}")
    print()


def choose_meeting(db: Database, rep: dict[str, Any], meetings: list[dict[str, Any]]) -> str:
    if not meetings:
        return create_fresh_meeting(db, rep)

    if len(meetings) == 1:
        meeting = meetings[0]
        print(f"{THEME.green}One upcoming meeting found. Auto-selecting it.{THEME.reset}\n")
        print_meeting_preview(db, meeting)
        input("Press Enter to generate the briefing...")
        return str(meeting["_id"])

    prompt = "Pick meeting number/id, press Enter for first, or type 'new': "
    choice = input(prompt).strip()

    if choice.lower() in {"new", "n", "create"}:
        return create_fresh_meeting(db, rep)

    if not choice:
        selected = meetings[0]
        print_meeting_preview(db, selected)
        proceed = input("Proceed with this meeting? [Y/n]: ").strip().lower()
        if proceed in {"", "y", "yes"}:
            return str(selected["_id"])
        return choose_meeting(db, rep, meetings)

    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(meetings):
            selected = meetings[index - 1]
            print_meeting_preview(db, selected)
            proceed = input("Proceed with this meeting? [Y/n]: ").strip().lower()
            if proceed in {"", "y", "yes"}:
                return str(selected["_id"])
            return choose_meeting(db, rep, meetings)

    selected = db["meetings"].find_one(
        {"_id": choice, "status": "scheduled", "rep_id": rep["_id"]}
    )
    if selected:
        print_meeting_preview(db, selected)
        proceed = input("Proceed with this meeting? [Y/n]: ").strip().lower()
        if proceed in {"", "y", "yes"}:
            return str(selected["_id"])

    print(f"{THEME.yellow}Meeting not found for this rep. Try a listed number or id.{THEME.reset}")
    return choose_meeting(db, rep, meetings)


async def run_pipeline_with_cli_logging(meeting_id: str) -> Any:
    session_service = InMemorySessionService()
    session_id = f"demo_session_{meeting_id}_{int(time.time())}"

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

    printer = StepPrinter()
    final_response_text = None

    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=message,
        ):
            author = getattr(event, "author", None)
            if author in STEP_LABELS:
                printer.start(author)

            if event.is_final_response() and event.content:
                for part in event.content.parts or []:
                    if part.text:
                        final_response_text = part.text

        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
        )
        state = session.state if session else {}
        compliance_result = parse_json_if_possible(state.get("compliance_result"))
        final_briefing = parse_json_if_possible(state.get("final_briefing"))

        action_detail = action_status_detail(final_briefing)
        printer.finish(detail=action_detail)

        if isinstance(compliance_result, dict):
            status = "passed" if compliance_result.get("passed") else "needs review"
            color = THEME.green if compliance_result.get("passed") else THEME.yellow
            print(f"{THEME.dim}Compliance result:{THEME.reset} {color}{status}{THEME.reset}")

        return final_briefing or parse_json_if_possible(final_response_text)

    except Exception:
        printer.finish(failed=True)
        raise


def action_status_detail(final_result: Any) -> str:
    if not isinstance(final_result, dict):
        return "Calendar skipped Gmail skipped MongoDB unknown"

    status = final_result.get("status")
    mongo_status = "MongoDB ✓" if status == "saved" else "MongoDB x"
    return f"Calendar skipped Gmail skipped {mongo_status}"


def print_final_briefing(result: Any) -> None:
    print(f"\n{THEME.bold}Final Briefing{THEME.reset}")
    print("-" * 92)

    if not isinstance(result, dict):
        print(result)
        return

    briefing = result.get("final_briefing") if isinstance(result.get("final_briefing"), dict) else result

    print(f"Status: {result.get('status', briefing.get('compliance_status', 'unknown'))}")
    print(f"Meeting: {result.get('meeting_id') or briefing.get('meeting_id', 'unknown')}")
    if result.get("briefing_id"):
        print(f"Briefing ID: {result['briefing_id']}")

    subject = briefing.get("draft_email_subject")
    if subject:
        print(f"\nEmail Subject:\n{subject}")

    drug_sections = briefing.get("drug_sections") or []
    if drug_sections:
        print("\nDrug Sections:")
        for section in drug_sections:
            print(f"\n{THEME.bold}{section.get('drug_name') or section.get('drug_id')}{THEME.reset}")
            for point in section.get("key_talking_points", []):
                if isinstance(point, dict):
                    text = point.get("point", "")
                    source = point.get("source", {})
                    source_id = source.get("pmid") or source.get("doc_id") or source.get("nct_id")
                    suffix = f" [{source_id}]" if source_id else ""
                    print(f"  - {text}{suffix}")
                else:
                    print(f"  - {point}")
    elif briefing.get("talking_points"):
        print("\nTalking Points:")
        for point in briefing["talking_points"]:
            print(f"  - {point}")

    email_body = briefing.get("draft_email_body")
    if email_body:
        print(f"\nEmail Body:\n{email_body}")

    rep_notes = briefing.get("rep_workflow_notes") or {}
    if rep_notes:
        print(f"\n{THEME.bold}Rep Workflow Notes{THEME.reset}")
        if rep_notes.get("objective"):
            print(f"Objective: {rep_notes['objective']}")
        for reminder in rep_notes.get("sample_reminders", []):
            print(f"  Sample: {reminder}")
        for reminder in rep_notes.get("follow_up_reminders", []):
            print(f"  Follow-up: {reminder}")

    flags = briefing.get("flags") or result.get("flags") or []
    if flags:
        print(f"\n{THEME.yellow}Compliance Flags:{THEME.reset}")
        for flag in flags:
            print(f"  - [{flag.get('severity')}] {flag.get('rule_id')}: {flag.get('reason')}")

    summary_report = briefing.get("rep_summary_report")
    if summary_report:
        print(f"\n{THEME.cyan}{THEME.bold}--- Prep Report for Sales Rep ---{THEME.reset}")
        print(summary_report)


def main() -> None:
    print_banner()
    total_started_at = time.perf_counter()
    client = None

    try:
        client, db = connect_db()
        rep = login_sales_rep(db)
        meetings = list_scheduled_meetings(db, rep)
        meeting_id = choose_meeting(db, rep, meetings)

        print(f"\n{THEME.bold}Running pipeline for {meeting_id}{THEME.reset}")
        print("-" * 92)
        result = asyncio.run(run_pipeline_with_cli_logging(meeting_id))

        print_final_briefing(result)
        print(f"\n{THEME.bold}Total time elapsed:{THEME.reset} {elapsed_text(total_started_at)}")

    except KeyboardInterrupt:
        print(f"\n{THEME.yellow}Demo interrupted by user.{THEME.reset}")
    except Exception as exc:
        print(f"\n{THEME.red}Demo failed:{THEME.reset} {exc}")
        raise
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
