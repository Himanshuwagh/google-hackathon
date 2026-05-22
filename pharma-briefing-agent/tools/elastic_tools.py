"""
elastic_tools.py — Elasticsearch Search Tool Functions for Google ADK Agents
==============================================================================
Pure Python functions that search Elasticsearch indices via elasticsearch-py.
Each function is registered as a tool for the ADK agent (Gemini).

Google ADK uses the docstrings to understand what each tool does,
what arguments it takes, and what it returns — so docstrings here
are critical and must be precise.

Indices:
  - idx_company_docs      — Drug datasheets + trial summaries
  - idx_crm_memory        — Past rep visit notes per HCP
  - idx_competitive_intel — Competitor analysis briefs

Connection uses config.py (ELASTIC_CLOUD_ID or ELASTIC_URL + ELASTIC_API_KEY).
BM25 text search only — no vector embeddings.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elasticsearch import Elasticsearch
from config import (
    ELASTIC_CLOUD_ID,
    ELASTIC_URL,
    ELASTIC_API_KEY,
    ELASTIC_IDX_COMPANY_DOCS,
    ELASTIC_IDX_CRM_MEMORY,
    ELASTIC_IDX_COMPETITIVE_INTEL,
)


# ── Shared Elasticsearch connection ───────────────────────────
def _get_es_client() -> Elasticsearch:
    """Create an Elasticsearch client using cloud_id or URL."""
    if ELASTIC_CLOUD_ID:
        return Elasticsearch(cloud_id=ELASTIC_CLOUD_ID, api_key=ELASTIC_API_KEY)
    elif ELASTIC_URL:
        return Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY)
    else:
        raise RuntimeError("No ELASTIC_CLOUD_ID or ELASTIC_URL configured in .env")


_es = _get_es_client()


def search_company_docs(query_text: str, drug_id: str) -> dict:
    """
    Searches the company documents index for drug clinical trial summaries,
    prescribing information, and datasheets relevant to a specific drug.

    Uses a bool query that combines full-text search on the content
    field with an exact-match filter on drug_id. Returns rich evidence
    objects including pdf_url (link to real published paper or internal
    document), source (journal citation), and description.

    The agent should call this when it needs drug-specific clinical
    data, prescribing information, or trial evidence to build
    talking points for a briefing. Include pdf_url and source in
    the evidence_ledger of the briefing for frontend display.

    Args:
        query_text: Natural language search query describing what
            information is needed (e.g. "renal protection outcomes
            in diabetic patients" or "dosage and side effects").
        drug_id: The exact drug_id to filter on, matching the _id
            field from the MongoDB drugs collection
            (e.g. "drug_lisinopril_10mg").

    Returns:
        A dict with the following structure:
        {
            "status": "success",
            "total_hits": 2,
            "results": [
                {
                    "doc_id": "cd_001",
                    "title": "ALLHAT Trial — Lisinopril vs Chlorthalidone...",
                    "description": "Landmark RCT comparing ACE inhibitor...",
                    "source": "JAMA, December 18, 2002 | PMID: 12479763",
                    "pdf_url": "https://pubmed.ncbi.nlm.nih.gov/12479763/",
                    "content": "...",
                    "score": 4.52,
                    "doc_type": "clinical_trial",
                    "tags": ["lisinopril", "ace-inhibitor"]
                },
                ...
            ]
        }
    """
    body = {
        "size": 5,
        "query": {
            "bool": {
                "must": [
                    {"match": {"content": query_text}}
                ],
                "filter": [
                    {"term": {"drug_id": drug_id}}
                ],
            }
        },
    }

    resp = _es.search(index=ELASTIC_IDX_COMPANY_DOCS, body=body)

    results = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        results.append({
            "doc_id": src.get("doc_id", hit["_id"]),
            "title": src.get("title", ""),
            "description": src.get("description", ""),
            "source": src.get("source", ""),
            "pdf_url": src.get("pdf_url", ""),
            "content": src.get("content", ""),
            "score": round(hit["_score"], 2),
            "doc_type": src.get("doc_type", ""),
            "tags": src.get("tags", []),
        })

    return {
        "status": "success",
        "total_hits": resp["hits"]["total"]["value"],
        "results": results,
    }


def search_crm_memory(hcp_id: str) -> dict:
    """Searches the CRM memory index for past interaction notes
    with a specific healthcare professional (doctor).

    Returns the most recent visit notes sorted by date descending.
    These notes contain valuable context about the doctor's
    preferences, objections, past requests, and sentiment —
    critical for personalising the briefing.

    The agent should call this to understand the relationship
    history before writing talking points.

    Args:
        hcp_id: The exact hcp_id to filter on, matching the _id
            field from the MongoDB hcp_profiles collection
            (e.g. "hcp_ananya_mehta").

    Returns:
        A dict with the following structure:
        {
            "status": "success",
            "total_hits": 3,
            "results": [
                {
                    "doc_id": "crm_003",
                    "hcp_id": "hcp_ananya_mehta",
                    "rep_id": "rep_rakesh_sharma",
                    "drug_ids": ["drug_lisinopril_10mg"],
                    "date": "2024-10-22",
                    "content": "..."
                },
                ...
            ]
        }
    """
    body = {
        "size": 5,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"hcp_id": hcp_id}}
                ],
            }
        },
        "sort": [
            {"date": {"order": "desc"}}
        ],
    }

    resp = _es.search(index=ELASTIC_IDX_CRM_MEMORY, body=body)

    results = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        results.append({
            "doc_id": src.get("doc_id", hit["_id"]),
            "hcp_id": src.get("hcp_id", ""),
            "rep_id": src.get("rep_id", ""),
            "drug_ids": src.get("drug_ids", []),
            "date": src.get("date", ""),
            "content": src.get("content", ""),
        })

    return {
        "status": "success",
        "total_hits": resp["hits"]["total"]["value"],
        "results": results,
    }


def search_competitive_intel(query_text: str, therapeutic_area: str) -> dict:
    """Searches the competitive intelligence index for competitor
    analysis briefs relevant to a therapeutic area.

    Uses a bool query combining full-text search on content with
    an exact-match filter on therapeutic_area. Returns competitor
    drug profiles, weaknesses, and counter-positioning strategies.

    The agent should call this to understand the competitive
    landscape before writing talking points, so it can proactively
    address competitor advantages and highlight differentiators.

    Args:
        query_text: Natural language search query describing the
            competitive context needed (e.g. "price comparison
            generic alternatives" or "Entresto heart failure").
        therapeutic_area: The therapeutic area to filter on
            (e.g. "cardiology", "endocrinology").

    Returns:
        A dict with the following structure:
        {
            "status": "success",
            "total_hits": 1,
            "results": [
                {
                    "doc_id": "ci_001",
                    "competitor_drug": "Generic Lisinopril (Cipla/Sun/Lupin)",
                    "therapeutic_area": "cardiology",
                    "our_drug_ids": ["drug_lisinopril_10mg"],
                    "content": "...",
                    "weakness_tags": ["no-patient-support", ...],
                    "score": 3.21
                },
                ...
            ]
        }
    """
    body = {
        "size": 3,
        "query": {
            "bool": {
                "must": [
                    {"match": {"content": query_text}}
                ],
                "filter": [
                    {"term": {"therapeutic_area": therapeutic_area}}
                ],
            }
        },
    }

    resp = _es.search(index=ELASTIC_IDX_COMPETITIVE_INTEL, body=body)

    results = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        results.append({
            "doc_id": src.get("doc_id", hit["_id"]),
            "competitor_drug": src.get("competitor_drug", ""),
            "therapeutic_area": src.get("therapeutic_area", ""),
            "our_drug_ids": src.get("our_drug_ids", []),
            "content": src.get("content", ""),
            "weakness_tags": src.get("weakness_tags", []),
            "score": round(hit["_score"], 2),
        })

    return {
        "status": "success",
        "total_hits": resp["hits"]["total"]["value"],
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════
# Test block — run: python tools/elastic_tools.py
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import pprint

    print("=" * 60)
    print("  elastic_tools.py — Test Run")
    print("=" * 60)

    # ── Test 1: search_company_docs ─────────────────────────
    print("\n🔍 Test 1: search_company_docs('renal protection diabetic', 'drug_lisinopril_10mg')")
    print("-" * 50)
    result1 = search_company_docs("renal protection diabetic", "drug_lisinopril_10mg")
    print(f"   Status: {result1['status']}")
    print(f"   Hits: {result1['total_hits']}")
    for r in result1["results"]:
        print(f"   📄 [{r['score']}] {r['title']}")
        print(f"      {r['content'][:100]}...")
    print()

    # ── Test 2: search_crm_memory ───────────────────────────
    print("🔍 Test 2: search_crm_memory('hcp_ananya_mehta')")
    print("-" * 50)
    result2 = search_crm_memory("hcp_ananya_mehta")
    print(f"   Status: {result2['status']}")
    print(f"   Hits: {result2['total_hits']}")
    for r in result2["results"]:
        print(f"   📝 [{r['date']}] {r['doc_id']}")
        print(f"      {r['content'][:100]}...")
    print()

    # ── Test 3: search_competitive_intel ────────────────────
    print("🔍 Test 3: search_competitive_intel('price generic market share', 'cardiology')")
    print("-" * 50)
    result3 = search_competitive_intel("price generic market share", "cardiology")
    print(f"   Status: {result3['status']}")
    print(f"   Hits: {result3['total_hits']}")
    for r in result3["results"]:
        print(f"   ⚔️  [{r['score']}] {r['competitor_drug']}")
        print(f"      Weaknesses: {r['weakness_tags']}")
        print(f"      {r['content'][:100]}...")
    print()

    # ── Test 4: search_crm_memory (Dr. Patel) ──────────────
    print("🔍 Test 4: search_crm_memory('hcp_vikram_patel')")
    print("-" * 50)
    result4 = search_crm_memory("hcp_vikram_patel")
    print(f"   Status: {result4['status']}")
    print(f"   Hits: {result4['total_hits']}")
    for r in result4["results"]:
        print(f"   📝 [{r['date']}] {r['doc_id']}")
        print(f"      {r['content'][:100]}...")

    print("\n✅ All tests complete.\n")
