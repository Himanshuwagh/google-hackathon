"""
seed_elastic.py — Seed Elasticsearch with 3 Indices
=====================================================
Creates and populates:
  1. idx_company_docs     — Drug clinical trials, prescribing info, datasheets (9 docs)
  2. idx_crm_memory       — Past rep visit notes per HCP (30 docs)
  3. idx_competitive_intel — Competitor analysis briefs (4 docs)

BM25 text search only — no dense_vector fields.
Uses delete_by_query + bulk index for idempotent re-runs.

Run:  python db/seed_elastic.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from config import (
    ELASTIC_CLOUD_ID,
    ELASTIC_URL,
    ELASTIC_API_KEY,
    ELASTIC_IDX_COMPANY_DOCS,
    ELASTIC_IDX_CRM_MEMORY,
    ELASTIC_IDX_COMPETITIVE_INTEL,
)


# ═══════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════
def load_json(filename: str) -> list:
    """Load JSON array from the data/ directory."""
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )
    with open(os.path.join(data_dir, filename), "r") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# INDEX MAPPINGS (BM25 text search — no vectors)
# ═══════════════════════════════════════════════════════════════
MAPPING_COMPANY_DOCS = {
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "drug_id": {"type": "keyword"},
            "therapeutic_area": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "standard"},
            "description": {"type": "text", "analyzer": "standard"},
            "source": {"type": "keyword"},
            "pdf_url": {"type": "keyword", "index": False},
            "content": {"type": "text", "analyzer": "standard"},
            "tags": {"type": "keyword"},
        }
    }
}

MAPPING_CRM_MEMORY = {
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "hcp_id": {"type": "keyword"},
            "rep_id": {"type": "keyword"},
            "drug_ids": {"type": "keyword"},
            "date": {"type": "date", "format": "yyyy-MM-dd"},
            "content": {"type": "text", "analyzer": "standard"},
        }
    }
}

MAPPING_COMPETITIVE_INTEL = {
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "competitor_drug": {"type": "keyword"},
            "therapeutic_area": {"type": "keyword"},
            "our_drug_ids": {"type": "keyword"},
            "content": {"type": "text", "analyzer": "standard"},
            "weakness_tags": {"type": "keyword"},
        }
    }
}


# ═══════════════════════════════════════════════════════════════
# CONNECTION HELPER
# ═══════════════════════════════════════════════════════════════
def connect_elasticsearch() -> Elasticsearch:
    """Connect using ELASTIC_CLOUD_ID (preferred) or ELASTIC_URL fallback."""
    if ELASTIC_CLOUD_ID:
        print(f"   Using Cloud ID: {ELASTIC_CLOUD_ID[:30]}...")
        return Elasticsearch(cloud_id=ELASTIC_CLOUD_ID, api_key=ELASTIC_API_KEY)
    elif ELASTIC_URL:
        print(f"   Using URL: {ELASTIC_URL}")
        return Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY)
    else:
        print("   ❌ No ELASTIC_CLOUD_ID or ELASTIC_URL set in .env")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# SEED FUNCTION
# ═══════════════════════════════════════════════════════════════
def seed_index(es: Elasticsearch, index_name: str, mapping: dict, docs: list):
    """Create (or recreate) an index and bulk-insert documents."""

    # ── Idempotent cleanup ──────────────────────────────────
    if es.indices.exists(index=index_name):
        # delete_by_query to clear all docs (preserves index if re-run)
        es.delete_by_query(
            index=index_name,
            body={"query": {"match_all": {}}},
            conflicts="proceed",
        )
        # Drop and recreate to ensure mapping is fresh
        es.indices.delete(index=index_name)

    # ── Create index ────────────────────────────────────────
    es.indices.create(index=index_name, body=mapping)

    # ── Bulk insert ─────────────────────────────────────────
    actions = [
        {
            "_index": index_name,
            "_id": doc["doc_id"],
            "_source": doc,
        }
        for doc in docs
    ]
    success, errors = bulk(es, actions, raise_on_error=False)

    # ── Refresh and count ───────────────────────────────────
    es.indices.refresh(index=index_name)
    count = es.count(index=index_name)["count"]

    return count, errors


def seed_elastic():
    """Main seeding function — connects and seeds all 3 indices."""

    print("=" * 60)
    print("  PharmaOps — Elasticsearch Seed Script")
    print("=" * 60)

    # ── Connect ─────────────────────────────────────────────
    print("\n🔗 Connecting to Elasticsearch...")
    es = connect_elasticsearch()

    try:
        info = es.info()
        print(f"   ✅ Connected to cluster: {info.get('cluster_name', 'unknown')}\n")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        sys.exit(1)

    # ── Load data from JSON files ───────────────────────────
    try:
        company_docs = load_json("elastic_company_docs.json")
        crm_memory = load_json("elastic_crm_memory.json")
        competitive_intel = load_json("elastic_competitive_intel.json")
    except FileNotFoundError as e:
        print(f"   ❌ Error loading data: {e}")
        sys.exit(1)

    # ── Seed each index ─────────────────────────────────────
    indices = [
        (ELASTIC_IDX_COMPANY_DOCS, MAPPING_COMPANY_DOCS, company_docs),
        (ELASTIC_IDX_CRM_MEMORY, MAPPING_CRM_MEMORY, crm_memory),
        (ELASTIC_IDX_COMPETITIVE_INTEL, MAPPING_COMPETITIVE_INTEL, competitive_intel),
    ]

    results = {}
    for index_name, mapping, docs in indices:
        print(f"   📦 Seeding '{index_name}' ({len(docs)} docs)...")
        count, errors = seed_index(es, index_name, mapping, docs)
        results[index_name] = count
        if errors:
            print(f"      ⚠️  {len(errors)} errors during bulk insert")
            for err in errors:
                print(f"         {err}")
        else:
            print(f"      ✅ {count} documents indexed")

    # ── Summary ─────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  SEED COMPLETE — Document Counts")
    print("=" * 60)
    for idx_name, count in results.items():
        print(f"   📊 {idx_name:<30s} → {count} docs")
    print(f"\n   Total: {sum(results.values())} documents across {len(results)} indices")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    seed_elastic()
