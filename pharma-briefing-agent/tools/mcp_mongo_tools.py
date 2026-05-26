"""ADK-facing MongoDB read tools backed by the active MCP runtime."""

from __future__ import annotations

from typing import Any

from tools.mongo_mcp_client import get_active_mongodb_mcp
from tools.mongo_tools import _normalize_drug_ids, _ordered_drugs


async def get_meeting(meeting_id: str) -> dict:
    """Fetch joined meeting context using the preflighted MongoDB MCP server.

    This is the canonical read path for briefing generation. It reads the
    meeting, sales rep, HCP, and drug documents through MongoDB MCP and returns
    the same structured context shape used by the planner prompt.
    """
    mcp = get_active_mongodb_mcp()
    meeting = await mcp.find_one("meetings", {"_id": meeting_id})
    if not meeting:
        return {"status": "not_found", "error": f"Meeting {meeting_id} not found"}

    rep = await mcp.find_one("sales_reps", {"_id": meeting["rep_id"]})
    hcp = await mcp.find_one("hcp_profiles", {"_id": meeting["hcp_id"]})
    drug_ids = _normalize_drug_ids(meeting)
    drugs: list[dict[str, Any]] = []
    if drug_ids:
        drugs = await mcp.find("drugs", {"_id": {"$in": drug_ids}}, limit=len(drug_ids))
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


async def get_compliance_rules() -> dict:
    """Fetch active pharmaceutical compliance rules through MongoDB MCP."""
    mcp = get_active_mongodb_mcp()
    rules = await mcp.find("compliance_rules", {}, limit=100)
    return {
        "status": "success",
        "count": len(rules),
        "rules": rules,
    }
