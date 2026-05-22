"""Deterministic evidence normalization and claim quality checks."""

import json
import re
from copy import deepcopy
from typing import Any


SOURCE_ID_KEYS = ("pmid", "doc_id", "nct_id", "nctId", "id", "source_id")
NUMERIC_RE = re.compile(
    r"(?i)(?:\bn\s*=\s*)?\d[\d,]*(?:\.\d+)?\s*(?:%|kg|mg|mmhg|weeks?|months?|years?|hours?|h\b|"
    r"patients?|adults?|mace|ci\b)?|hr\s*0?\.\d+|p\s*[<=>]\s*0?\.\d+|95%\s*ci"
)
VAGUE_CLAIM_RE = re.compile(
    r"(?i)\b(significant|effective|benefits?|efficacy|improved|strong|meaningful|substantial)\b"
)
OUTCOME_NUMBER_RE = re.compile(
    r"(?i)(\d[\d,]*(?:\.\d+)?\s*(?:%|kg|mmhg)|hr\s*0?\.\d+|"
    r"p\s*[<=>]\s*0?\.\d+|95%\s*ci\s*[,\s]*\d|ci\s*\d)"
)


def parse_json_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def extract_numbers(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    seen: set[str] = set()
    numbers: list[str] = []
    for match in NUMERIC_RE.finditer(text):
        number = re.sub(r"\s+", " ", match.group(0)).strip()
        key = number.lower()
        if key and key not in seen:
            numbers.append(number)
            seen.add(key)
    return numbers


def _sentence_claims(text: str) -> list[str]:
    claims = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        sentence = sentence.strip()
        if sentence and extract_numbers(sentence):
            claims.append(sentence[:500])
    return claims[:6]


def _source_id(source: dict[str, Any]) -> str:
    for key in SOURCE_ID_KEYS:
        value = source.get(key)
        if value:
            return str(value)
    return ""


def _has_outcome_number_in_text(text: str) -> bool:
    return bool(OUTCOME_NUMBER_RE.search(text))


def _source_key(source_type: str, source_id: str) -> tuple[str, str]:
    return (source_type.lower(), source_id.lower())


def _contains_any(text: str, terms: list[str]) -> bool:
    normalized = text.lower()
    return any(term and term.lower() in normalized for term in terms)


def _class_terms(drug: dict[str, Any]) -> list[str]:
    values = [
        drug.get("drug_class", ""),
        drug.get("therapeutic_area", ""),
        drug.get("drug_name", ""),
    ]
    text = " ".join(str(value).lower() for value in values)
    terms: list[str] = []
    if "glp" in text or "glyde" in text:
        terms.extend(["glp-1", "glp 1", "glucagon-like peptide-1", "semaglutide"])
    if "sglt" in text:
        terms.extend(["sglt-2", "sglt2", "sodium-glucose co-transporter-2"])
    if "ace inhibitor" in text or "lisinopril" in text:
        terms.extend(["ace inhibitor", "lisinopril"])
    if "calcium channel" in text or "amlodipine" in text:
        terms.extend(["calcium channel", "amlodipine"])
    if "egfr" in text or "targotinib" in text:
        terms.extend(["egfr", "tyrosine kinase inhibitor", "tki"])
    return terms


def classify_source_scope(source_text: str, drug: dict[str, Any]) -> str:
    """Classify whether a source can support a drug-specific claim."""
    text = source_text.lower()
    brand = str(drug.get("drug_name") or "").lower()
    generic = str(drug.get("generic_name") or "").lower()

    if brand and brand in text:
        return "direct_brand"
    if generic and generic in text:
        return "generic_molecule"

    background_terms = ["background metformin", "metformin therapy", "with metformin", "without metformin"]
    if "metformin" in text and not _contains_any(text, [brand, generic]):
        return "background_therapy"
    if any(term in text for term in background_terms):
        return "background_therapy"

    if _contains_any(text, _class_terms(drug)):
        return "class_or_analog"
    return "class_or_analog"


def _ledger_entry(
    *,
    drug: dict[str, Any],
    source_type: str,
    source_id: str,
    title: str,
    source_text: str,
    source_scope: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = {
        "drug_id": drug.get("drug_id"),
        "drug_name": drug.get("drug_name"),
        "source_type": source_type,
        "source_id": source_id,
        "title": title,
        "source_scope": source_scope,
        "claim_role": "supporting" if source_scope not in {"background_therapy", "competitor"} else source_scope,
        "verbatim_numbers": extract_numbers(source_text),
        "supported_claims": _sentence_claims(source_text),
    }
    if extra:
        entry.update(extra)
    return entry


def build_evidence_ledger(retrieved_context: Any) -> list[dict[str, Any]]:
    """Build one normalized ledger from retriever raw tool outputs."""
    context = parse_json_if_possible(retrieved_context)
    if not isinstance(context, dict):
        return []

    ledger: list[dict[str, Any]] = []
    for drug_id, payload in (context.get("per_drug") or {}).items():
        if not isinstance(payload, dict):
            continue
        drug = {
            "drug_id": payload.get("drug_id") or drug_id,
            "drug_name": payload.get("drug_name") or drug_id,
            "generic_name": payload.get("generic_name", ""),
            "drug_class": payload.get("drug_class", ""),
            "therapeutic_area": payload.get("therapeutic_area", ""),
        }

        for doc in ((payload.get("company_docs") or {}).get("results") or []):
            text = " ".join(str(doc.get(key, "")) for key in ("title", "content"))
            ledger.append(
                _ledger_entry(
                    drug=drug,
                    source_type="InternalDoc",
                    source_id=str(doc.get("doc_id", "")),
                    title=str(doc.get("title", "")),
                    source_text=text,
                    source_scope="direct_brand",
                    extra={
                        "doc_type": doc.get("doc_type"),
                        "tags": doc.get("tags", []),
                        "pdf_url": doc.get("pdf_url", ""),
                        "source": doc.get("source", ""),
                        "description": doc.get("description", ""),
                    },
                )
            )

        for doc in ((payload.get("competitive_intel") or {}).get("results") or []):
            text = " ".join(str(doc.get(key, "")) for key in ("competitor_drug", "content"))
            ledger.append(
                _ledger_entry(
                    drug=drug,
                    source_type="CompetitiveIntel",
                    source_id=str(doc.get("doc_id", "")),
                    title=str(doc.get("competitor_drug") or doc.get("title", "")),
                    source_text=text,
                    source_scope="competitor",
                    extra={"competitor_drug": doc.get("competitor_drug")},
                )
            )

        for article in ((payload.get("pubmed") or {}).get("results") or []):
            text = " ".join(str(article.get(key, "")) for key in ("title", "abstract_snippet"))
            pmid = str(article.get("pmid", ""))
            ledger.append(
                _ledger_entry(
                    drug=drug,
                    source_type="PubMed",
                    source_id=pmid,
                    title=str(article.get("title", "")),
                    source_text=text,
                    source_scope=classify_source_scope(text, drug),
                    extra={
                        "pmid": pmid,
                        "pub_date": article.get("pub_date"),
                        "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    },
                )
            )

        for trial in ((payload.get("clinical_trials") or {}).get("results") or []):
            text = " ".join(str(trial.get(key, "")) for key in ("briefTitle", "phase", "enrollment"))
            nct_id = str(trial.get("nctId", ""))
            ledger.append(
                _ledger_entry(
                    drug=drug,
                    source_type="ClinicalTrials",
                    source_id=nct_id,
                    title=str(trial.get("briefTitle", "")),
                    source_text=text,
                    source_scope=classify_source_scope(text, drug),
                    extra={"nct_id": nct_id, "enrollment": trial.get("enrollment"), "phase": trial.get("phase")},
                )
            )
    return [entry for entry in ledger if entry.get("source_id")]


def attach_evidence_ledger(retrieved_context: Any) -> Any:
    context = parse_json_if_possible(retrieved_context)
    if not isinstance(context, dict):
        return retrieved_context
    context["evidence_ledger"] = build_evidence_ledger(context)
    return context


def _collect_cited_evidence(clean_brief: dict[str, Any], ledger_by_key: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for section in clean_brief.get("drug_sections") or []:
        for point in section.get("key_talking_points") or []:
            source = point.get("source") or {}
            if not isinstance(source, dict):
                continue
            source_type = str(source.get("type") or source.get("source_type") or "")
            source_id = _source_id(source)
            key = _source_key(source_type, source_id)
            if not source_id or key in seen:
                continue
            ledger_entry = ledger_by_key.get(key, {})
            item = {
                "source": source_type,
                "type": source_type,
                "id": source_id,
                "source_id": source_id,
                "title": source.get("title") or ledger_entry.get("title"),
                "relevance": point.get("point", "")[:240],
                "drug_id": section.get("drug_id") or ledger_entry.get("drug_id"),
                "source_scope": ledger_entry.get("source_scope"),
            }
            if source_type == "PubMed":
                item["pmid"] = source_id
                item["source_url"] = ledger_entry.get("source_url") or f"https://pubmed.ncbi.nlm.nih.gov/{source_id}/"
            elif source_type == "ClinicalTrials":
                item["nctId"] = source_id
            elif source_type in {"InternalDoc", "CompetitiveIntel"}:
                item["doc_id"] = source_id
                item["pdf_url"] = ledger_entry.get("pdf_url", "")
                item["source_citation"] = ledger_entry.get("source", "")
            evidence.append(item)
            seen.add(key)
    return evidence


def validate_claim_quality(draft_brief: Any, retrieved_context: Any) -> dict[str, Any]:
    """Validate talking points against the evidence ledger and enrich evidence."""
    brief = parse_json_if_possible(draft_brief)
    context = attach_evidence_ledger(retrieved_context)
    if not isinstance(brief, dict):
        return {
            "passed": False,
            "flags": [{"rule_id": "claim_quality_json", "offending_text": "", "reason": "draft_brief is not valid JSON", "severity": "blocker"}],
            "clean_brief": {},
        }

    clean_brief = deepcopy(brief)
    ledger = context.get("evidence_ledger", []) if isinstance(context, dict) else []
    ledger_by_key = {
        _source_key(str(entry.get("source_type", "")), str(entry.get("source_id", ""))): entry
        for entry in ledger
    }
    flags: list[dict[str, Any]] = []

    for section in clean_brief.get("drug_sections") or []:
        drug_id = section.get("drug_id")
        for point in section.get("key_talking_points") or []:
            text = str(point.get("point", ""))
            source = point.get("source") or {}
            if not isinstance(source, dict):
                source = {}
            source_type = str(source.get("type") or source.get("source_type") or "")
            source_id = _source_id(source)
            specific_numbers = point.get("specific_numbers") or []

            if VAGUE_CLAIM_RE.search(text) and not _has_outcome_number_in_text(text):
                flags.append({"rule_id": "claim_quality_specificity", "offending_text": text, "reason": "Talking point uses vague efficacy language without exact numeric data.", "severity": "blocker"})
            if not _has_outcome_number_in_text(text):
                flags.append({"rule_id": "claim_quality_numbers", "offending_text": text, "reason": "Talking point must include the exact outcome number in the sentence itself, not only in metadata.", "severity": "blocker"})
            if not source_id:
                flags.append({"rule_id": "claim_quality_source", "offending_text": text, "reason": "Talking point lacks a specific source ID.", "severity": "blocker"})
                continue

            ledger_entry = ledger_by_key.get(_source_key(source_type, source_id))
            if not ledger_entry:
                flags.append({"rule_id": "claim_quality_source", "offending_text": text, "reason": f"Source {source_type}:{source_id} is not present in the evidence ledger.", "severity": "blocker"})
                continue
            if ledger_entry.get("drug_id") != drug_id:
                flags.append({"rule_id": "claim_quality_drug_ownership", "offending_text": text, "reason": f"Source belongs to {ledger_entry.get('drug_id')} but talking point is for {drug_id}.", "severity": "blocker"})
            if ledger_entry.get("source_scope") in {"background_therapy", "competitor"} and source_type == "PubMed":
                flags.append({"rule_id": "claim_quality_source_scope", "offending_text": text, "reason": f"PubMed source {source_id} is classified as {ledger_entry.get('source_scope')} and cannot support a featured-drug claim.", "severity": "blocker"})

    clean_brief["supporting_evidence"] = _collect_cited_evidence(clean_brief, ledger_by_key)
    clean_brief["evidence_ledger"] = ledger
    clean_brief["quality_gate_status"] = "passed" if not flags else "failed"
    if flags:
        clean_brief["draft_warnings"] = (clean_brief.get("draft_warnings") or []) + [
            f"{flag['rule_id']}: {flag['reason']}" for flag in flags
        ]

    return {
        "passed": not flags,
        "flags": flags,
        "clean_brief": clean_brief,
        "evidence_ledger": ledger,
    }
