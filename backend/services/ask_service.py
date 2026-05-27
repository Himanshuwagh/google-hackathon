import json
import logging
import os
import re
from typing import Any

from google import genai
from google.genai import types

from runtime_config import configure_environment
from services.meeting_service import get_meeting_context


logger = logging.getLogger("pharmaops.ask_service")

DEFAULT_ASK_MODEL = "gemini-3.1-flash-lite"
DEFAULT_ASK_FALLBACK_MODELS = ("gemini-2.5-flash-lite", "gemini-2.5-flash")

SYSTEM_PROMPT = """
You are a pharma sales intelligence assistant. You have full context about
a specific doctor meeting including clinical evidence, compliance rules, and
doctor profile. Answer the rep's question accurately and concisely using
only the provided context.

Style:
- Be short by default. For simple factual questions, answer in 1 sentence.
- Use 2-4 bullets only when the user asks for a list, plan, objection handling,
  evidence summary, or next steps.
- Give a longer answer only when the question clearly requires clinical detail,
  comparison, strategy, or compliance nuance.
- Answer only what was asked; do not add unrelated coaching.
- Do not show citations, source IDs, source labels, or a "Sources" section in
  the chat answer. Use the provided evidence internally for accuracy.

Safety:
- Never make claims that would violate UCPMP 2024 rules.
- Never mention off-label uses.
"""


def _split_model_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _ask_model_candidates() -> list[str]:
    """Return chat-specific model candidates.

    Do not read GEMINI_MODEL here. That variable is shared with the briefing
    pipeline and can be pinned to a model whose model-specific quota is
    unavailable while newer Gemini models still work for the same key/project.
    """
    primary_models = _split_model_list(
        os.getenv("ASK_GEMINI_MODEL") or os.getenv("GEMINI_CHAT_MODEL") or DEFAULT_ASK_MODEL
    )
    fallback_models = _split_model_list(os.getenv("ASK_GEMINI_FALLBACK_MODELS")) or list(
        DEFAULT_ASK_FALLBACK_MODELS
    )

    candidates: list[str] = []
    for model in [*primary_models, *fallback_models]:
        if model not in candidates:
            candidates.append(model)
    return candidates


def _compact_error_message(exc: Exception) -> str:
    detail = re.sub(r"\s+", " ", str(exc)).strip()
    if "RESOURCE_EXHAUSTED" in detail or "quota" in detail.lower():
        return "The Gemini request reached the configured quota limit. Please retry after quota resets or use a key/project with available quota."
    if len(detail) > 220:
        detail = f"{detail[:217]}..."
    return f"The answer service could not complete this request: {detail}"


def _clean_chat_answer(answer: str) -> str:
    """Remove source artifacts from answers before they are shown in chat."""
    cleaned = re.sub(r"\n+\s*(?:Sources?|References?)\s*:.*\Z", "", answer, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\s*\((?:Source|Sources|Reference|References)\s*:[^)]+\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\[(?:Source|Sources|Reference|References)\s*:[^\]]+\]", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


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

Answer the question directly. Keep it as short as the question allows. Do not
display citations, source IDs, or a sources section.
"""

    try:
        client = _client()
        last_error: Exception | None = None
        answer = ""
        for model in _ask_model_candidates():
            try:
                logger.info("[ASK] Generating answer for meeting_id=%s with model=%s", meeting_id, model)
                response = client.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                answer = getattr(response, "text", None) or str(response)
                break
            except Exception as model_error:
                last_error = model_error
                detail = str(model_error)
                if "RESOURCE_EXHAUSTED" in detail or "quota" in detail.lower():
                    logger.warning(
                        "[ASK] Model quota exhausted for meeting_id=%s model=%s; trying fallback if available",
                        meeting_id,
                        model,
                    )
                    continue
                raise
        if not answer and last_error:
            raise last_error
    except Exception as exc:
        logger.error("[ASK] Failed to answer meeting_id=%s: %s", meeting_id, exc, exc_info=True)
        answer = _compact_error_message(exc)

    return {
        "answer": _clean_chat_answer(answer),
        "sources": sources,
        "meeting_id": meeting_id,
    }
