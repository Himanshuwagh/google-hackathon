"""MongoDB Atlas hybrid retrieval tools for Google ADK agents.

These functions replace the former external search-service tools while preserving
their public return shapes. MongoDB Atlas stores the document corpora, vector
embeddings, source metadata, and operational agent memory.
"""

from __future__ import annotations

import math
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient

from config import (
    GEMINI_EMBEDDING_DIM,
    GEMINI_EMBEDDING_MODEL,
    MONGO_DB_NAME,
    MONGO_URI,
)


COMPANY_DOCS_COLLECTION = "company_docs"
CRM_MEMORY_COLLECTION = "crm_memory"
COMPETITIVE_INTEL_COLLECTION = "competitive_intel"
RRF_K = 60

_client: MongoClient | None = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client[MONGO_DB_NAME]
    return _db


def _collection(name: str):
    return _get_db()[name]


def embedding_text_for_document(document: dict[str, Any], *, kind: str) -> str:
    """Build normalized text used for embeddings and fallback text scoring."""
    if kind == "company_docs":
        fields = [
            document.get("title", ""),
            document.get("description", ""),
            document.get("source", ""),
            document.get("doc_type", ""),
            " ".join(document.get("tags") or []),
            document.get("content", ""),
        ]
    elif kind == "competitive_intel":
        fields = [
            document.get("competitor_drug", ""),
            document.get("therapeutic_area", ""),
            " ".join(document.get("weakness_tags") or []),
            document.get("content", ""),
        ]
    else:
        fields = [
            document.get("date", ""),
            " ".join(document.get("drug_ids") or []),
            document.get("content", ""),
        ]
    return re.sub(r"\s+", " ", " ".join(str(field) for field in fields if field)).strip()


def _google_client():
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    project = os.getenv("GOOGLE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
    if api_key:
        return genai.Client(api_key=api_key)
    if project:
        return genai.Client(vertexai=True, project=project, location=location)
    return genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def embed_text(text: str) -> list[float]:
    """Generate a Gemini embedding for MongoDB Atlas Vector Search."""
    if not text.strip():
        return []

    response = _google_client().models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=[text],
        config={"output_dimensionality": GEMINI_EMBEDDING_DIM},
    )
    embeddings = getattr(response, "embeddings", None) or []
    if not embeddings:
        return []
    values = getattr(embeddings[0], "values", None)
    return list(values or [])


def with_embedding_metadata(document: dict[str, Any], *, kind: str) -> dict[str, Any]:
    """Return a copy of document with embedding fields populated."""
    item = dict(document)
    text = embedding_text_for_document(item, kind=kind)
    item["embedding_text"] = text
    item["embedding_model"] = GEMINI_EMBEDDING_MODEL
    item["embedding_dim"] = GEMINI_EMBEDDING_DIM
    item["embedding"] = embed_text(text)
    item["updated_at"] = datetime.now(timezone.utc)
    return item


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2]


def _fallback_text_score(query_text: str, document: dict[str, Any], *, kind: str) -> float:
    query_tokens = _tokens(query_text)
    if not query_tokens:
        return 0.0
    text = embedding_text_for_document(document, kind=kind).lower()
    score = 0.0
    for token in query_tokens:
        occurrences = text.count(token)
        if occurrences:
            score += 1.0 + math.log(occurrences)
    return score


def _vector_search(
    collection_name: str,
    query_text: str,
    filter_query: dict[str, Any],
    *,
    index_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    try:
        vector = embed_text(query_text)
    except Exception:
        return []
    if not vector:
        return []

    pipeline = [
        {
            "$vectorSearch": {
                "index": index_name,
                "path": "embedding",
                "queryVector": vector,
                "numCandidates": max(limit * 20, 50),
                "limit": limit,
                "filter": filter_query,
            }
        },
        {"$addFields": {"_vector_score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"embedding": 0}},
    ]
    try:
        return list(_collection(collection_name).aggregate(pipeline))
    except Exception:
        return []


def _atlas_text_search(
    collection_name: str,
    query_text: str,
    filter_query: dict[str, Any],
    *,
    index_name: str,
    paths: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    compound: dict[str, Any] = {
        "must": [
            {
                "text": {
                    "query": query_text,
                    "path": paths,
                    "fuzzy": {"maxEdits": 1, "prefixLength": 3},
                }
            }
        ]
    }
    filters = _atlas_equals_filters(filter_query)
    if filters:
        compound["filter"] = filters

    pipeline = [
        {"$search": {"index": index_name, "compound": compound}},
        {"$limit": limit},
        {"$addFields": {"_text_score": {"$meta": "searchScore"}}},
        {"$project": {"embedding": 0}},
    ]
    try:
        return list(_collection(collection_name).aggregate(pipeline))
    except Exception:
        return []


def _atlas_equals_filters(filter_query: dict[str, Any]) -> list[dict[str, Any]]:
    filters = []
    for field, value in filter_query.items():
        if isinstance(value, dict) and "$in" in value:
            filters.append({"in": {"path": field, "value": value["$in"]}})
        else:
            filters.append({"equals": {"path": field, "value": value}})
    return filters


def _fallback_text_search(
    collection_name: str,
    query_text: str,
    filter_query: dict[str, Any],
    *,
    kind: str,
    limit: int,
) -> list[dict[str, Any]]:
    documents = list(_collection(collection_name).find(filter_query, {"embedding": 0}))
    ranked = []
    for document in documents:
        score = _fallback_text_score(query_text, document, kind=kind)
        if score > 0:
            item = dict(document)
            item["_text_score"] = score
            ranked.append(item)
    ranked.sort(key=lambda item: item.get("_text_score", 0), reverse=True)
    return ranked[:limit]


def _doc_key(document: dict[str, Any]) -> str:
    return str(document.get("doc_id") or document.get("_id"))


def _rrf_merge(
    vector_results: list[dict[str, Any]],
    text_results: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for source_name, results in (("vector", vector_results), ("text", text_results)):
        for rank, document in enumerate(results, 1):
            key = _doc_key(document)
            if not key:
                continue
            entry = merged.setdefault(key, dict(document))
            entry["_rrf_score"] = entry.get("_rrf_score", 0.0) + (1.0 / (RRF_K + rank))
            entry.setdefault("_matched_by", [])
            if source_name not in entry["_matched_by"]:
                entry["_matched_by"].append(source_name)
            if "_vector_score" in document:
                entry["_vector_score"] = document["_vector_score"]
            if "_text_score" in document:
                entry["_text_score"] = document["_text_score"]

    ranked = sorted(merged.values(), key=lambda item: item.get("_rrf_score", 0), reverse=True)
    return ranked[:limit]


def _hybrid_search(
    collection_name: str,
    query_text: str,
    filter_query: dict[str, Any],
    *,
    kind: str,
    vector_index: str,
    search_index: str,
    text_paths: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    vector_results = _vector_search(
        collection_name,
        query_text,
        filter_query,
        index_name=vector_index,
        limit=limit,
    )
    text_results = _atlas_text_search(
        collection_name,
        query_text,
        filter_query,
        index_name=search_index,
        paths=text_paths,
        limit=limit,
    )
    if not text_results:
        text_results = _fallback_text_search(
            collection_name,
            query_text,
            filter_query,
            kind=kind,
            limit=limit,
        )
    return _rrf_merge(vector_results, text_results, limit=limit)


def search_company_docs(query_text: str, drug_id: str) -> dict:
    """Search MongoDB Atlas company documents for drug-specific evidence.

    Uses MongoDB Atlas Vector Search plus Atlas text search when available,
    with an exact drug_id filter. Returns the legacy search result shape used
    by the retriever, writer, and evidence ledger.
    """
    results = _hybrid_search(
        COMPANY_DOCS_COLLECTION,
        query_text,
        {"drug_id": drug_id},
        kind="company_docs",
        vector_index="company_docs_vector_index",
        search_index="company_docs_search_index",
        text_paths=["title", "description", "content", "tags", "source", "doc_type"],
        limit=5,
    )

    return {
        "status": "success",
        "retrieval_backend": "mongodb_atlas_hybrid",
        "total_hits": len(results),
        "results": [
            {
                "doc_id": item.get("doc_id", _doc_key(item)),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "source": item.get("source", ""),
                "pdf_url": item.get("pdf_url", ""),
                "content": item.get("content", ""),
                "score": round(float(item.get("_rrf_score", item.get("_text_score", 0))), 4),
                "doc_type": item.get("doc_type", ""),
                "tags": item.get("tags", []),
            }
            for item in results
        ],
    }


def search_crm_memory(hcp_id: str) -> dict:
    """Fetch the latest MongoDB CRM memory notes for a healthcare professional."""
    documents = list(
        _collection(CRM_MEMORY_COLLECTION)
        .find({"hcp_id": hcp_id}, {"embedding": 0})
        .sort("date", -1)
        .limit(5)
    )
    return {
        "status": "success",
        "retrieval_backend": "mongodb_atlas",
        "total_hits": len(documents),
        "results": [
            {
                "doc_id": item.get("doc_id", _doc_key(item)),
                "hcp_id": item.get("hcp_id", ""),
                "rep_id": item.get("rep_id", ""),
                "drug_ids": item.get("drug_ids", []),
                "date": item.get("date", ""),
                "content": item.get("content", ""),
            }
            for item in documents
        ],
    }


def search_competitive_intel(query_text: str, therapeutic_area: str) -> dict:
    """Search MongoDB Atlas competitive intelligence for a therapeutic area."""
    results = _hybrid_search(
        COMPETITIVE_INTEL_COLLECTION,
        query_text,
        {"therapeutic_area": therapeutic_area},
        kind="competitive_intel",
        vector_index="competitive_intel_vector_index",
        search_index="competitive_intel_search_index",
        text_paths=["competitor_drug", "therapeutic_area", "content", "weakness_tags"],
        limit=3,
    )

    return {
        "status": "success",
        "retrieval_backend": "mongodb_atlas_hybrid",
        "total_hits": len(results),
        "results": [
            {
                "doc_id": item.get("doc_id", _doc_key(item)),
                "competitor_drug": item.get("competitor_drug", ""),
                "therapeutic_area": item.get("therapeutic_area", ""),
                "our_drug_ids": item.get("our_drug_ids", []),
                "content": item.get("content", ""),
                "weakness_tags": item.get("weakness_tags", []),
                "score": round(float(item.get("_rrf_score", item.get("_text_score", 0))), 4),
            }
            for item in results
        ],
    }
