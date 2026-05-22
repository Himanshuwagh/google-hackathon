"""
seed_data.py — Seed MongoDB with Demo Data from JSON files
============================================================
Seeds source data collections: sales_reps, hcp_profiles, drugs, meetings,
and compliance_rules. Generated briefings are intentionally not seeded.

Run:  python db/seed_data.py
"""

import os
import sys
import json
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from config import MONGO_URI, MONGO_DB_NAME

def load_json_data(filename):
    """Loads JSON data from the data directory."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    filepath = os.path.join(data_dir, filename)
    with open(filepath, 'r') as f:
        return json.load(f)

# ═══════════════════════════════════════════════════════════════
# SEED FUNCTION
# ═══════════════════════════════════════════════════════════════
def seed_mongodb():
    """Connect to MongoDB Atlas and seed all collections with demo data."""

    print("=" * 60)
    print("  PharmaOps — MongoDB Seed Script")
    print("=" * 60)

    # ── Connect ─────────────────────────────────────────────
    print(f"\\n🔗 Connecting to MongoDB Atlas...")
    print(f"   Database: {MONGO_DB_NAME}")
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]

    # Verify connection
    try:
        client.admin.command("ping")
        print("   ✅ Connected successfully!\\n")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        sys.exit(1)

    # ── Load Data ───────────────────────────────────────────
    try:
        sales_reps = load_json_data("sales_reps.json")
        hcp_profiles = load_json_data("hcp_profiles.json")
        drugs = load_json_data("drugs.json")
        meetings = load_json_data("meetings.json")
        compliance_rules = load_json_data("compliance_rules.json")
    except FileNotFoundError as e:
        print(f"   ❌ Error loading JSON data: {e}")
        sys.exit(1)

    # ── Seed each collection ────────────────────────────────
    collections_to_seed = [
        ("sales_reps", sales_reps),
        ("hcp_profiles", hcp_profiles),
        ("drugs", drugs),
        ("meetings", meetings),
        ("compliance_rules", compliance_rules),
        ("briefings", []),
    ]

    for collection_name, documents in collections_to_seed:
        coll = db[collection_name]

        # Drop existing data for clean re-seed
        existing_count = coll.count_documents({})
        if existing_count > 0:
            print(f"   🗑️  Dropping {existing_count} existing docs from '{collection_name}'")
            coll.delete_many({})

        # Insert
        if documents:
            result = coll.insert_many(documents)
            print(f"   ✅ Seeded '{collection_name}' — {len(result.inserted_ids)} documents")
        else:
            print(f"   ⚠️  No documents to seed for '{collection_name}'")

    # ── Summary ─────────────────────────────────────────────
    print("\\n" + "=" * 60)
    print("  SEED COMPLETE — Collection Summary")
    print("=" * 60)
    for name in ["sales_reps", "hcp_profiles", "drugs", "meetings", "compliance_rules", "briefings"]:
        count = db[name].count_documents({})
        print(f"   📦 {name:<20s} → {count} documents")
    print()

    client.close()
    print("🔒 Connection closed. Done!\\n")

if __name__ == "__main__":
    seed_mongodb()
