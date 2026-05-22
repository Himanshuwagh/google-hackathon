"""
mongo_tools.py — MongoDB Tool Functions for Google ADK Agents
==============================================================
Pure Python functions that read/write to MongoDB via pymongo.
Each function is registered as a tool for the ADK agent (Gemini).

Google ADK uses the docstrings to understand what each tool does,
what arguments it takes, and what it returns — so docstrings here
are critical and must be precise.

Connection uses config.py (MONGO_URI, MONGO_DB_NAME).
"""

import json
import os
import sys
from datetime import datetime, timezone

# Add project root to path so config can be imported from anywhere
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from config import MONGO_URI, MONGO_DB_NAME


# ── Shared MongoDB connection ─────────────────────────────────
# Lazily initialized so importing agent prompts/tests does not trigger network.
_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client[MONGO_DB_NAME]
    return _db


def _normalize_drug_ids(meeting: dict) -> list[str]:
    """Return ordered drug IDs from either MVP+ or legacy meeting shape."""
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
    elif isinstance(legacy_drug_id, str) and legacy_drug_id not in normalized:
        normalized.append(legacy_drug_id)

    detailing_sequence = meeting.get("detailing_sequence")
    if isinstance(detailing_sequence, list):
        sequence = [drug_id for drug_id in detailing_sequence if drug_id in normalized]
        remaining = [drug_id for drug_id in normalized if drug_id not in sequence]
        normalized = sequence + remaining

    return normalized


def _ordered_drugs(drugs: list[dict], drug_ids: list[str]) -> list[dict]:
    """Sort fetched drug documents to match the normalized meeting order."""
    order = {drug_id: index for index, drug_id in enumerate(drug_ids)}
    return sorted(drugs, key=lambda drug: order.get(drug.get("_id"), len(order)))


def get_meeting(meeting_id: str) -> dict:
    """Fetches a meeting document from MongoDB and joins it with the
    associated sales rep profile, HCP (doctor) profile, and drug profiles
    to return a single combined context object.

    This is the first tool the agent should call when processing a new
    meeting. The returned object contains everything needed to plan
    the briefing: doctor specialty, known objections, drug indications,
    approved claims, rep preferences, meeting objective, planned samples,
    pending action items, detailing sequence, and meeting logistics.

    Meeting schema compatibility:
        - Legacy MVP meetings may include drug_id: "drug_lisinopril_10mg".
        - MVP+ meetings may include drug_ids: ["drug_a", "drug_b"] and an
          optional detailing_sequence to control primary/secondary order.

    Args:
        meeting_id: The _id of the meeting document in the meetings
            collection (e.g. "mtg_001").

    Returns:
        A dict with the following structure:
        {
            "status": "found",
            "meeting": { ... meeting fields ... },
            "rep": { ... sales rep profile ... },
            "hcp": { ... doctor profile ... },
            "drug_ids": ["..."],
            "drugs": [{ ... drug profile with indications, claims ... }],
            "drug": { ... first drug profile, for backward compatibility ... }
        }
        If the meeting is not found, returns:
        {"status": "not_found", "error": "Meeting <id> not found"}
    """
    # Fetch the meeting document
    db = _get_db()
    meeting = db["meetings"].find_one({"_id": meeting_id})
    if not meeting:
        return {"status": "not_found", "error": f"Meeting {meeting_id} not found"}

    # Fetch the joined profiles using foreign keys from the meeting
    rep = db["sales_reps"].find_one({"_id": meeting["rep_id"]})
    hcp = db["hcp_profiles"].find_one({"_id": meeting["hcp_id"]})
    drug_ids = _normalize_drug_ids(meeting)
    drugs = []
    if drug_ids:
        drugs = list(db["drugs"].find({"_id": {"$in": drug_ids}}))
        drugs = _ordered_drugs(drugs, drug_ids)

    missing_drug_ids = [
        drug_id for drug_id in drug_ids if drug_id not in {drug.get("_id") for drug in drugs}
    ]
    first_drug = drugs[0] if drugs else None

    return {
        "status": "found",
        "meeting": meeting,
        "rep": rep if rep else {"error": f"Rep {meeting['rep_id']} not found"},
        "hcp": hcp if hcp else {"error": f"HCP {meeting['hcp_id']} not found"},
        "drug_ids": drug_ids,
        "drugs": drugs,
        "drug": first_drug
        if first_drug
        else {"error": f"No drugs found for meeting {meeting_id}", "missing_drug_ids": drug_ids},
        "missing_drug_ids": missing_drug_ids,
    }


def get_compliance_rules() -> dict:
    """Fetches all active pharmaceutical compliance rules from the
    compliance_rules collection in MongoDB.

    These rules are sourced from India's UCPMP 2024 (Uniform Code for
    Pharmaceutical Marketing Practices). The agent must check every
    talking point in a briefing against these rules before saving.

    Rules with severity "blocker" must never be violated — the briefing
    must be rewritten if any blocker rule is failed. Rules with severity
    "warning" should be flagged but do not block the briefing.

    Args:
        (none)

    Returns:
        A dict with the following structure:
        {
            "status": "success",
            "count": 8,
            "rules": [ { rule_id, source, rule_text, category, severity }, ... ]
        }
    """
    db = _get_db()
    cursor = db["compliance_rules"].find({})
    rules = list(cursor)

    return {
        "status": "success",
        "count": len(rules),
        "rules": rules,
    }


def save_briefing(briefing_data: str) -> dict:
    """Saves a completed briefing document to the briefings collection
    in MongoDB.

    The agent calls this after the briefing has passed compliance checks.
    The briefing_data argument must be a JSON string representing the
    full briefing object including: meeting_id, hcp_id, rep_id,
    talking_points, supporting_evidence, compliance_status,
    draft_email_subject, draft_email_body, etc.

    The function automatically adds a generated_at timestamp.

    Args:
        briefing_data: A JSON string containing the briefing document.
            Must include at minimum:
            - meeting_id (str): ID of the meeting this briefing is for
            - hcp_id (str): ID of the doctor
            - rep_id (str): ID of the sales rep
            - talking_points (list[str]): The briefing talking points
            - compliance_status (str): "passed" or "failed"

    Returns:
        A dict with the following structure on success:
        {"status": "saved", "briefing_id": "brief_mtg001_..."}
        On parse error:
        {"status": "error", "error": "Failed to parse briefing_data: ..."}
    """
    try:
        briefing = json.loads(briefing_data)
    except (json.JSONDecodeError, TypeError) as e:
        return {"status": "error", "error": f"Failed to parse briefing_data: {str(e)}"}

    # Generate a briefing ID if not provided
    if "_id" not in briefing:
        meeting_id = briefing.get("meeting_id", "unknown")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        briefing["_id"] = f"brief_{meeting_id}_{timestamp}"

    # Add generation timestamp
    briefing["generated_at"] = datetime.now(timezone.utc).isoformat()
    briefing["source"] = "agent_generated"
    briefing["generated_by"] = "pharma_adk_pipeline"

    # Insert into MongoDB
    db = _get_db()
    result = db["briefings"].insert_one(briefing)

    return {
        "status": "saved",
        "briefing_id": str(result.inserted_id),
    }


def update_meeting_status(meeting_id: str, status: str, briefing_id: str) -> dict:
    """Updates a meeting document in MongoDB after the agent has finished
    processing it.

    Sets the meeting status (e.g. from "scheduled" to "briefing_ready"),
    links the generated briefing, and marks the agent_triggered flag
    as True so the change stream listener does not re-process it.

    Args:
        meeting_id: The _id of the meeting document to update
            (e.g. "mtg_001").
        status: The new status value to set. Expected values:
            "briefing_ready", "processing", "failed".
        briefing_id: The _id of the briefing document that was saved
            for this meeting (e.g. "brief_mtg001_20250609021400").

    Returns:
        A dict with the following structure on success:
        {"status": "updated", "meeting_id": "mtg_001", "new_status": "briefing_ready"}
        If the meeting is not found:
        {"status": "not_found", "error": "Meeting <id> not found"}
    """
    db = _get_db()
    result = db["meetings"].update_one(
        {"_id": meeting_id},
        {
            "$set": {
                "status": status,
                "briefing_id": briefing_id,
                "agent_triggered": True,
            }
        },
    )

    if result.matched_count == 0:
        return {"status": "not_found", "error": f"Meeting {meeting_id} not found"}

    return {
        "status": "updated",
        "meeting_id": meeting_id,
        "new_status": status,
    }


# ═══════════════════════════════════════════════════════════════
# Test block — run: python tools/mongo_tools.py
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import pprint

    print("=" * 60)
    print("  mongo_tools.py — Test Run")
    print("=" * 60)

    # ── Test 1: get_meeting ─────────────────────────────────
    print("\n🔍 Test: get_meeting('mtg_001')")
    print("-" * 40)
    result = get_meeting("mtg_001")
    pprint.pprint(result, width=100)

    # ── Test 2: get_compliance_rules ────────────────────────
    print("\n📋 Test: get_compliance_rules()")
    print("-" * 40)
    rules_result = get_compliance_rules()
    print(f"   Status: {rules_result['status']}")
    print(f"   Rule count: {rules_result['count']}")
    for rule in rules_result["rules"]:
        severity_icon = "🔴" if rule["severity"] == "blocker" else "🟡"
        print(f"   {severity_icon} [{rule['rule_id']}] {rule['rule_text'][:70]}...")

    # ── Test 3: get_meeting (not found) ─────────────────────
    print("\n❌ Test: get_meeting('mtg_999') — should return not_found")
    print("-" * 40)
    result_404 = get_meeting("mtg_999")
    pprint.pprint(result_404)

    print("\n✅ All tests complete.\n")

    _client.close()
