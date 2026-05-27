"""Seed MongoDB Atlas retrieval collections from local JSON fixtures.

Creates and populates:
  - company_docs
  - crm_memory
  - competitive_intel

Company docs and competitive intel receive Gemini embeddings for Atlas Vector
Search. CRM memory is indexed for HCP/date lookup and can be embedded later if
needed, but runtime retrieval prioritizes recent HCP-specific notes.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import OperationFailure

from config import GEMINI_EMBEDDING_DIM, MONGO_DB_NAME, MONGO_URI
from tools.mongo_retrieval_tools import with_embedding_metadata


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_json(filename: str) -> list[dict[str, Any]]:
    with (DATA_DIR / filename).open(encoding="utf-8") as data_file:
        return json.load(data_file)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_collection(collection, documents: list[dict[str, Any]], *, kind: str, embed: bool) -> int:
    collection.delete_many({})
    prepared = []
    for document in documents:
        item = dict(document)
        item["_id"] = item.get("doc_id")
        item["corpus_kind"] = kind
        item["updated_at"] = _now()
        if embed:
            item = with_embedding_metadata(item, kind=kind)
        prepared.append(item)
    if prepared:
        collection.insert_many(prepared)
    return collection.count_documents({})


def _create_indexes(db) -> None:
    db["company_docs"].create_index([("doc_id", ASCENDING)], unique=True)
    db["company_docs"].create_index([("drug_id", ASCENDING)])
    db["company_docs"].create_index([("therapeutic_area", ASCENDING)])
    db["company_docs"].create_index([("tags", ASCENDING)])
    db["company_docs"].create_index(
        [("title", "text"), ("description", "text"), ("content", "text"), ("tags", "text")],
        name="company_docs_text",
    )

    db["crm_memory"].create_index([("doc_id", ASCENDING)], unique=True)
    db["crm_memory"].create_index([("hcp_id", ASCENDING), ("date", DESCENDING)])
    db["crm_memory"].create_index([("rep_id", ASCENDING)])
    db["crm_memory"].create_index([("drug_ids", ASCENDING)])
    db["crm_memory"].create_index([("content", "text")], name="crm_memory_text")

    db["competitive_intel"].create_index([("doc_id", ASCENDING)], unique=True)
    db["competitive_intel"].create_index([("therapeutic_area", ASCENDING)])
    db["competitive_intel"].create_index([("our_drug_ids", ASCENDING)])
    db["competitive_intel"].create_index([("weakness_tags", ASCENDING)])
    db["competitive_intel"].create_index(
        [("competitor_drug", "text"), ("content", "text"), ("weakness_tags", "text")],
        name="competitive_intel_text",
    )


def _create_atlas_search_indexes(db) -> None:
    """Best-effort Atlas Search index creation.

    PyMongo forwards createSearchIndexes to Atlas clusters that support it.
    Local MongoDB/community deployments will raise; regular indexes and runtime
    fallback search still work there.
    """
    search_indexes = {
        "company_docs": [
            {
                "name": "company_docs_vector_index",
                "definition": {
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": GEMINI_EMBEDDING_DIM,
                            "similarity": "cosine",
                        },
                        {"type": "filter", "path": "drug_id"},
                        {"type": "filter", "path": "therapeutic_area"},
                    ]
                },
            },
            {
                "name": "company_docs_search_index",
                "definition": {"mappings": {"dynamic": True}},
            },
        ],
        "competitive_intel": [
            {
                "name": "competitive_intel_vector_index",
                "definition": {
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": GEMINI_EMBEDDING_DIM,
                            "similarity": "cosine",
                        },
                        {"type": "filter", "path": "therapeutic_area"},
                        {"type": "filter", "path": "our_drug_ids"},
                    ]
                },
            },
            {
                "name": "competitive_intel_search_index",
                "definition": {"mappings": {"dynamic": True}},
            },
        ],
    }

    for collection_name, indexes in search_indexes.items():
        for index in indexes:
            try:
                db.command(
                    {
                        "createSearchIndexes": collection_name,
                        "indexes": [index],
                    }
                )
                print(f"   Created Atlas Search index {collection_name}.{index['name']}")
            except OperationFailure as exc:
                if "already exists" in str(exc).lower():
                    print(f"   Atlas Search index already exists: {collection_name}.{index['name']}")
                else:
                    print(f"   Skipped Atlas Search index {collection_name}.{index['name']}: {exc.details or exc}")


def seed_mongodb_retrieval() -> None:
    print("=" * 60)
    print("  PharmaOps - MongoDB Retrieval Seed Script")
    print("=" * 60)

    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    client.admin.command("ping")
    print(f"   Connected to MongoDB database: {MONGO_DB_NAME}")

    corpora = [
        ("company_docs", load_json("mongo_company_docs.json"), "company_docs", True),
        ("crm_memory", load_json("mongo_crm_memory.json"), "crm_memory", False),
        ("competitive_intel", load_json("mongo_competitive_intel.json"), "competitive_intel", True),
    ]
    for collection_name, documents, kind, embed in corpora:
        print(f"   Seeding {collection_name} ({len(documents)} docs, embeddings={embed})")
        count = _seed_collection(db[collection_name], documents, kind=kind, embed=embed)
        print(f"      {count} documents ready")

    _create_indexes(db)
    _create_atlas_search_indexes(db)

    print("=" * 60)
    print("  MongoDB retrieval seed complete")
    print("=" * 60)
    client.close()


if __name__ == "__main__":
    seed_mongodb_retrieval()
