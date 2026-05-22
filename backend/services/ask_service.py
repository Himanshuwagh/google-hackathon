import json
import os
import re
from typing import Any

from google import genai
from google.genai import types

from runtime_config import configure_environment
from services.meeting_service import get_meeting_context


SYSTEM_PROMPT = """
You are a pharma sales intelligence assistant. You have full context about
a specific doctor meeting including clinical evidence, compliance rules, and
doctor profile. Answer the rep's question accurately and concisely using
only the provided context. Cite your sources. Never make claims that would
violate UCPMP 2024 rules. Never mention off-label uses.
"""


def _compact_error_message(exc: Exception) -> str:
    detail = re.sub(r"\s+", " ", str(exc)).strip()
    if "RESOURCE_EXHAUSTED" in detail or "quota" in detail.lower():
        return "The Gemini request reached the configured quota limit. Please retry after quota resets or use a key/project with available quota."
    if len(detail) > 220:
        detail = f"{detail[:217]}..."
    return f"The answer service could not complete this request: {detail}"


def _client() -> genai.Client:
    configure_environment()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)

    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_PROJECT_ID")
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GOOGLE_LOCATION") or "us-central1"
    if project:
        return genai.Client(vertexai=True, project=project, location=location)
    return genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def _source_candidates(context: dict[str, Any]) -> list[dict[str, Any]]:
    briefing = context.get("briefing") or {}
    sources: list[dict[str, Any]] = []
    for evidence in briefing.get("supporting_evidence", []) or []:
        sources.append(
            {
                "type": evidence.get("source", "internal").lower(),
                "id": evidence.get("id") or evidence.get("source_id"),
                "label": evidence.get("title") or evidence.get("label") or evidence.get("source"),
            }
        )
    for evidence in briefing.get("evidence_ledger", []) or []:
        sources.append(
            {
                "type": evidence.get("source_type", "internal"),
                "id": evidence.get("source_id"),
                "label": evidence.get("title"),
                "scope": evidence.get("source_scope"),
            }
        )
    for point in briefing.get("talking_points", []) or []:
        if isinstance(point, dict) and point.get("source_id"):
            sources.append(
                {
                    "type": point.get("source_type", "internal"),
                    "id": point.get("source_id"),
                    "label": point.get("source_label") or point.get("citation"),
                }
            )
    for section in briefing.get("drug_sections", []) or []:
        for point in section.get("key_talking_points", []) or []:
            if not isinstance(point, dict):
                continue
            source = point.get("source") or {}
            if not isinstance(source, dict):
                continue
            source_id = source.get("pmid") or source.get("doc_id") or source.get("nct_id") or source.get("nctId") or source.get("id")
            if source_id:
                sources.append(
                    {
                        "type": source.get("type", "internal"),
                        "id": source_id,
                        "label": source.get("title") or point.get("point"),
                    }
                )
    deduped = []
    seen = set()
    for source in sources:
        key = (source.get("type"), source.get("id"), source.get("label"))
        if key not in seen:
            deduped.append(source)
            seen.add(key)
    return deduped


async def answer_question(meeting_id: str, question: str) -> dict[str, Any] | None:
    context = await get_meeting_context(meeting_id)
    if not context:
        return None

    hcp = context.get("hcp") or {}
    drug = context.get("drug") or {}
    briefing = context.get("briefing") or {}
    compliance_rules = context.get("compliance_rules") or []
    sources = _source_candidates(context)

    user_prompt = f"""
Meeting context:
- Doctor: {hcp.get("name")}, {hcp.get("specialty")}, {hcp.get("hospital")}
- Drug: {drug.get("brand_name") or drug.get("drug_name") or drug.get("name")} ({drug.get("drug_class") or drug.get("class")})
- Known objections: {hcp.get("known_objections", [])}
- Talking points already prepared: {briefing.get("talking_points", [])}
- Drug sections prepared: {briefing.get("drug_sections", [])}
- Clinical evidence available: {briefing.get("supporting_evidence", [])}
- Evidence ledger: {briefing.get("evidence_ledger", [])}
- Compliance rules to follow: {compliance_rules}

Rep's question: {question}

Answer in 2-4 paragraphs. Be specific. Cite trial data where relevant.
"""

    try:
        client = _client()
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            contents=user_prompt,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        answer = getattr(response, "text", None) or str(response)
    except Exception as exc:
        answer = _compact_error_message(exc)

    return {
        "answer": answer.strip(),
        "sources": sources,
        "meeting_id": meeting_id,
    }
