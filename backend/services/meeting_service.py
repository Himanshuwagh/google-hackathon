import logging
from datetime import UTC, datetime, time
from typing import Any, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from bson import ObjectId

from db import COLLECTIONS, get_database
from models.meeting import NewMeetingRequest

logger = logging.getLogger("pharmaops.meeting_service")

DISPLAY_TIMEZONE = ZoneInfo("Asia/Kolkata")
REAL_BRIEFING_FILTER = {
    "$or": [
        {"source": "agent_generated"},
        {"generated_by": "pharma_adk_pipeline"},
    ]
}


def _display_time(value: datetime) -> str:
    value = _to_display_datetime(value)
    hour = value.hour % 12 or 12
    suffix = "AM" if value.hour < 12 else "PM"
    return f"{hour}:{value.minute:02d} {suffix}"


def _ensure_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise ValueError("Invalid meeting_date value")


def _to_display_datetime(value: datetime) -> datetime:
    value = _ensure_datetime(value)
    return value.astimezone(DISPLAY_TIMEZONE)


def _local_date_key(value: datetime) -> str:
    return _to_display_datetime(value).date().isoformat()


def _date_range_bounds(start_date: str, end_date: str) -> tuple[datetime, datetime, str, str]:
    start_local = datetime.combine(datetime.fromisoformat(start_date).date(), time.min, tzinfo=DISPLAY_TIMEZONE)
    end_local = datetime.combine(datetime.fromisoformat(end_date).date(), time.max, tzinfo=DISPLAY_TIMEZONE)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)
    return (
        start_utc,
        end_utc,
        start_utc.isoformat().replace("+00:00", "Z"),
        end_utc.isoformat().replace("+00:00", "Z"),
    )


def _serialize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _public_hcp(hcp: Optional[dict[str, Any]]) -> dict[str, Any]:
    hcp = hcp or {}
    result = dict(hcp)
    if "_id" in result:
        result["id"] = result.pop("_id")
    return result


def _public_drug(drug: Optional[dict[str, Any]]) -> dict[str, Any]:
    drug = drug or {}
    return {
        "id": drug.get("_id"),
        "brand_name": drug.get("brand_name") or drug.get("drug_name") or drug.get("name"),
        "drug_class": drug.get("drug_class") or drug.get("class"),
    }


def _briefing_id(briefing: dict[str, Any]) -> str | None:
    return briefing.get("briefing_id") or briefing.get("_id")


def _primary_drug_id(meeting: dict[str, Any]) -> str | None:
    if meeting.get("drug_id"):
        return meeting["drug_id"]
    drug_ids = meeting.get("drug_ids") or []
    return drug_ids[0] if drug_ids else None


def _real_briefing_query(extra_filter: dict[str, Any]) -> dict[str, Any]:
    return {"$and": [extra_filter, REAL_BRIEFING_FILTER]}


async def _find_briefing_for_meeting(meeting: dict[str, Any]) -> dict[str, Any] | None:
    """Find existing briefing for a meeting with multi-tier fallback.

    Lookup order:
    1. By meeting.briefing_id with source filter (exact match)
    2. By meeting._id with source filter (meeting_id lookup)
    3. Fallback: ANY briefing matching the meeting_id (without source filter)
    4. Fallback: ANY briefing matching the briefing_id (without source filter)

    This ensures we never miss a briefing that exists in MongoDB, even if
    the source/generated_by markers are missing or different.
    """
    db = get_database()
    meeting_id = meeting.get("_id")
    briefing_id_field = meeting.get("briefing_id")

    logger.info(
        "[FIND_BRIEFING] Starting lookup for meeting_id=%s, meeting.briefing_id=%s",
        meeting_id,
        briefing_id_field,
    )

    # ── Tier 1: Look up by briefing_id with source filter ──
    if briefing_id_field:
        try:
            briefing = await db[COLLECTIONS["briefings"]].find_one(
                _real_briefing_query({"_id": briefing_id_field})
            )
            if briefing:
                logger.info("[FIND_BRIEFING] Found by _id=%s (tier 1a, filtered)", briefing_id_field)
                return briefing

            briefing = await db[COLLECTIONS["briefings"]].find_one(
                _real_briefing_query({"briefing_id": briefing_id_field})
            )
            if briefing:
                logger.info("[FIND_BRIEFING] Found by briefing_id=%s (tier 1b, filtered)", briefing_id_field)
                return briefing

            logger.debug(
                "[FIND_BRIEFING] Tier 1 miss: no filtered match for briefing_id=%s",
                briefing_id_field,
            )
        except Exception as exc:
            logger.error("[FIND_BRIEFING] Tier 1 DB error: %s", exc, exc_info=True)

    # ── Tier 2: Look up by meeting_id with source filter ──
    try:
        briefing = await db[COLLECTIONS["briefings"]].find_one(
            _real_briefing_query({"meeting_id": meeting_id}),
            sort=[("generated_at", -1)],
        )
        if briefing:
            logger.info(
                "[FIND_BRIEFING] Found by meeting_id=%s (tier 2, filtered), briefing._id=%s",
                meeting_id,
                briefing.get("_id"),
            )
            return briefing
        logger.debug("[FIND_BRIEFING] Tier 2 miss: no filtered match for meeting_id=%s", meeting_id)
    except Exception as exc:
        logger.error("[FIND_BRIEFING] Tier 2 DB error: %s", exc, exc_info=True)

    # ── Tier 3 (Fallback): ANY briefing matching meeting_id, no source filter ──
    try:
        briefing = await db[COLLECTIONS["briefings"]].find_one(
            {"meeting_id": meeting_id},
            sort=[("generated_at", -1)],
        )
        if briefing:
            logger.warning(
                "[FIND_BRIEFING] Found by meeting_id=%s (tier 3, UNFILTERED fallback), "
                "briefing._id=%s, source=%s, generated_by=%s — consider backfilling markers",
                meeting_id,
                briefing.get("_id"),
                briefing.get("source"),
                briefing.get("generated_by"),
            )
            return briefing
    except Exception as exc:
        logger.error("[FIND_BRIEFING] Tier 3 DB error: %s", exc, exc_info=True)

    # ── Tier 4 (Fallback): ANY briefing matching briefing_id, no source filter ──
    if briefing_id_field:
        try:
            briefing = await db[COLLECTIONS["briefings"]].find_one(
                {"$or": [{"_id": briefing_id_field}, {"briefing_id": briefing_id_field}]}
            )
            if briefing:
                logger.warning(
                    "[FIND_BRIEFING] Found by briefing_id=%s (tier 4, UNFILTERED fallback), "
                    "source=%s, generated_by=%s",
                    briefing_id_field,
                    briefing.get("source"),
                    briefing.get("generated_by"),
                )
                return briefing
        except Exception as exc:
            logger.error("[FIND_BRIEFING] Tier 4 DB error: %s", exc, exc_info=True)

    logger.info("[FIND_BRIEFING] No briefing found for meeting_id=%s after all tiers", meeting_id)
    return None


def _public_status(meeting: dict[str, Any], briefing: dict[str, Any] | None) -> str:
    status = meeting.get("status", "scheduled")
    if briefing and status == "scheduled":
        return "briefing_ready"
    if not briefing and status == "briefing_ready":
        return "scheduled"
    return status


async def list_meetings(
    rep_id: str,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    db = get_database()
    query_start = start_date or date
    query_end = end_date or date
    if not query_start or not query_end:
        raise ValueError("date or start_date/end_date is required")

    start, end, start_iso, end_iso = _date_range_bounds(query_start, query_end)

    meetings = await db[COLLECTIONS["meetings"]].find(
        {
            "rep_id": rep_id,
            "$or": [
                {"meeting_date": {"$gte": start, "$lte": end}},
                {"meeting_date": {"$gte": start_iso, "$lte": end_iso}},
            ],
        }
    ).sort("meeting_date", 1).to_list(length=None)

    hcp_ids = list({meeting.get("hcp_id") for meeting in meetings if meeting.get("hcp_id")})
    drug_ids = [
        _primary_drug_id(meeting)
        for meeting in meetings
        if _primary_drug_id(meeting)
    ]
    hcp_map = {
        doc["_id"]: doc
        for doc in await db[COLLECTIONS["hcp_profiles"]].find(
            {"_id": {"$in": hcp_ids}}
        ).to_list(length=None)
    }
    drug_map = {
        doc["_id"]: doc
        for doc in await db[COLLECTIONS["drugs"]].find(
            {"_id": {"$in": drug_ids}}
        ).to_list(length=None)
    }
    meeting_ids = [meeting["_id"] for meeting in meetings]
    briefing_map = {
        doc["meeting_id"]: doc
        for doc in await db[COLLECTIONS["briefings"]].find(
            _real_briefing_query({"meeting_id": {"$in": meeting_ids}})
        ).sort("generated_at", -1).to_list(length=None)
        if doc.get("meeting_id")
    }

    items = []
    for meeting in meetings:
        hcp = hcp_map.get(meeting.get("hcp_id"), {})
        drug = drug_map.get(_primary_drug_id(meeting), {})
        briefing = briefing_map.get(meeting["_id"])
        briefing_id = _briefing_id(briefing) if briefing else None
        status = _public_status(meeting, briefing)
        meeting_date = _ensure_datetime(meeting["meeting_date"])
        display_date = _to_display_datetime(meeting_date)
        items.append(
            {
                "meeting_id": meeting["_id"],
                "hcp_name": hcp.get("name", ""),
                "hcp_specialty": hcp.get("specialty", ""),
                "hospital": hcp.get("hospital", ""),
                "drug_name": drug.get("brand_name") or drug.get("drug_name") or drug.get("name", ""),
                "meeting_date": display_date,
                "meeting_date_key": _local_date_key(meeting_date),
                "meeting_time_display": _display_time(meeting_date),
                "duration_mins": meeting.get("duration_mins", 20),
                "status": status,
                "briefing_id": briefing_id,
                "error_message": meeting.get("error_message") or meeting.get("agent_error"),
            }
        )
    return items


async def get_meeting_form_options(rep_id: str) -> dict[str, list[dict[str, Any]]]:
    del rep_id
    db = get_database()
    hcps = await db[COLLECTIONS["hcp_profiles"]].find({}).sort("name", 1).to_list(length=None)
    drugs = await db[COLLECTIONS["drugs"]].find({}).sort("brand_name", 1).to_list(length=None)

    return {
        "hcps": [
            {
                "id": _serialize(hcp.get("_id")),
                "name": hcp.get("name", ""),
                "specialty": hcp.get("specialty", ""),
                "hospital": hcp.get("hospital", ""),
                "city": hcp.get("city", ""),
                "relationship_score": hcp.get("relationship_score"),
            }
            for hcp in hcps
        ],
        "drugs": [
            {
                "id": _serialize(drug.get("_id")),
                "brand_name": drug.get("brand_name") or drug.get("drug_name") or drug.get("name", ""),
                "generic_name": drug.get("generic_name", ""),
                "drug_class": drug.get("drug_class") or drug.get("class", ""),
            }
            for drug in drugs
        ],
    }


async def create_meeting(payload: NewMeetingRequest) -> str:
    db = get_database()
    meeting_id = f"mtg_{uuid4().hex[:8]}"
    meeting_date = _ensure_datetime(payload.meeting_date)
    document = {
        "_id": meeting_id,
        "rep_id": payload.rep_id,
        "hcp_id": payload.hcp_id,
        "drug_id": payload.drug_id,
        "drug_ids": [payload.drug_id],
        "meeting_date": meeting_date,
        "location": payload.location,
        "duration_mins": payload.duration_mins,
        "status": "scheduled",
        "agent_triggered": False,
        "briefing_id": None,
    }
    await db[COLLECTIONS["meetings"]].insert_one(document)
    return meeting_id


async def get_meeting_detail(meeting_id: str) -> Optional[dict[str, Any]]:
    logger.info("[GET_DETAIL] Fetching meeting detail for meeting_id=%s", meeting_id)
    db = get_database()

    try:
        meeting = await db[COLLECTIONS["meetings"]].find_one({"_id": meeting_id})
    except Exception as exc:
        logger.error("[GET_DETAIL] DB error fetching meeting %s: %s", meeting_id, exc, exc_info=True)
        return None

    if not meeting:
        logger.warning("[GET_DETAIL] Meeting not found: %s", meeting_id)
        return None

    logger.info(
        "[GET_DETAIL] Meeting found: id=%s, status=%s, briefing_id=%s",
        meeting_id,
        meeting.get("status"),
        meeting.get("briefing_id"),
    )

    try:
        hcp = await db[COLLECTIONS["hcp_profiles"]].find_one({"_id": meeting.get("hcp_id")})
    except Exception as exc:
        logger.error("[GET_DETAIL] DB error fetching HCP: %s", exc)
        hcp = None

    drug_id = _primary_drug_id(meeting)
    try:
        drug = await db[COLLECTIONS["drugs"]].find_one({"_id": drug_id}) if drug_id else None
    except Exception as exc:
        logger.error("[GET_DETAIL] DB error fetching drug: %s", exc)
        drug = None

    try:
        briefing = await _find_briefing_for_meeting(meeting)
    except Exception as exc:
        logger.error("[GET_DETAIL] Error in _find_briefing_for_meeting: %s", exc, exc_info=True)
        briefing = None

    briefing_id = _briefing_id(briefing) if briefing else meeting.get("briefing_id")
    status = _public_status(meeting, briefing)
    if not briefing:
        briefing_id = None
    if briefing:
        briefing["briefing_id"] = _briefing_id(briefing)
        briefing = _serialize(briefing)

    logger.info(
        "[GET_DETAIL] Returning: meeting_id=%s, status=%s, has_briefing=%s, briefing_id=%s",
        meeting_id,
        status,
        briefing is not None,
        briefing_id,
    )

    meeting_date = _ensure_datetime(meeting["meeting_date"])
    display_date = _to_display_datetime(meeting_date)
    return {
        "meeting_id": meeting["_id"],
        "status": status,
        "hcp": _serialize(_public_hcp(hcp)),
        "drug": _serialize(_public_drug(drug)),
        "meeting_date": display_date,
        "meeting_date_key": _local_date_key(meeting_date),
        "meeting_time_display": _display_time(meeting_date),
        "duration_mins": meeting.get("duration_mins", 20),
        "location": meeting.get("location"),
        "error_message": meeting.get("error_message") or meeting.get("agent_error"),
        "briefing_id": briefing_id,
        "briefing": briefing,
    }


async def get_meeting_context(meeting_id: str) -> Optional[dict[str, Any]]:
    db = get_database()
    meeting = await db[COLLECTIONS["meetings"]].find_one({"_id": meeting_id})
    if not meeting:
        return None

    hcp = await db[COLLECTIONS["hcp_profiles"]].find_one({"_id": meeting.get("hcp_id")})
    drug_id = _primary_drug_id(meeting)
    drug = await db[COLLECTIONS["drugs"]].find_one({"_id": drug_id}) if drug_id else None
    briefing = await _find_briefing_for_meeting(meeting)
    rules = await db[COLLECTIONS["compliance_rules"]].find({}).to_list(length=None)
    return _serialize(
        {
            "meeting": meeting,
            "hcp": hcp,
            "drug": drug,
            "briefing": briefing,
            "compliance_rules": rules,
        }
    )


async def request_briefing_generation(
    meeting_id: str,
    force: bool = False,
) -> tuple[Optional[dict[str, Any]], bool]:
    logger.info(
        "[REQ_GENERATION] Briefing generation requested: meeting_id=%s, force=%s",
        meeting_id,
        force,
    )
    db = get_database()

    try:
        meeting = await db[COLLECTIONS["meetings"]].find_one({"_id": meeting_id})
    except Exception as exc:
        logger.error("[REQ_GENERATION] DB error fetching meeting: %s", exc, exc_info=True)
        return None, False

    if not meeting:
        logger.warning("[REQ_GENERATION] Meeting not found: %s", meeting_id)
        return None, False

    logger.info(
        "[REQ_GENERATION] Meeting status=%s, agent_triggered=%s",
        meeting.get("status"),
        meeting.get("agent_triggered"),
    )

    if meeting.get("status") == "agent_processing":
        logger.info("[REQ_GENERATION] Already processing, not re-triggering")
        return await get_meeting_detail(meeting_id), False

    if force:
        logger.info("[REQ_GENERATION] Force regeneration — deleting existing briefings")
        await db[COLLECTIONS["briefings"]].delete_many(
            _real_briefing_query({"meeting_id": meeting_id})
        )
        if meeting.get("briefing_id"):
            await db[COLLECTIONS["briefings"]].delete_many(
                _real_briefing_query(
                    {
                        "$or": [
                            {"_id": meeting["briefing_id"]},
                            {"briefing_id": meeting["briefing_id"]},
                        ]
                    }
                )
            )
        # Also delete unfiltered briefings for a truly clean slate
        await db[COLLECTIONS["briefings"]].delete_many({"meeting_id": meeting_id})
    else:
        existing = await _find_briefing_for_meeting(meeting)
        if existing:
            logger.info(
                "[REQ_GENERATION] Existing briefing found (id=%s), skipping generation",
                existing.get("_id"),
            )
            return await get_meeting_detail(meeting_id), False

    logger.info("[REQ_GENERATION] Setting meeting status to agent_processing")
    result = await db[COLLECTIONS["meetings"]].update_one(
        {
            "_id": meeting_id,
            "status": {"$in": ["scheduled", "briefing_ready", "needs_review", "failed"]},
        },
        {
            "$set": {
                "status": "agent_processing",
                "agent_triggered": True,
            },
            "$unset": {
                "briefing_id": "",
                "error_message": "",
                "agent_error": "",
            },
        },
    )

    should_start = result.modified_count == 1
    logger.info("[REQ_GENERATION] Update result: modified_count=%d, should_start=%s", result.modified_count, should_start)
    return await get_meeting_detail(meeting_id), should_start


async def update_meeting_status(
    meeting_id: str,
    status: str,
    briefing_id: str | None = None,
    error_message: str | None = None,
    agent_triggered: bool | None = None,
) -> None:
    logger.info(
        "[UPDATE_STATUS] meeting_id=%s, status=%s, briefing_id=%s, error=%s",
        meeting_id,
        status,
        briefing_id,
        error_message,
    )
    db = get_database()
    updates: dict[str, Any] = {"status": status}
    if briefing_id is not None:
        updates["briefing_id"] = briefing_id
    if error_message is not None:
        updates["error_message"] = error_message
    if agent_triggered is not None:
        updates["agent_triggered"] = agent_triggered
    await db[COLLECTIONS["meetings"]].update_one({"_id": meeting_id}, {"$set": updates})
