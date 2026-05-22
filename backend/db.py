import os
from functools import lru_cache

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from runtime_config import configure_environment

configure_environment()

COLLECTIONS = {
    "meetings": "meetings",
    "hcp_profiles": "hcp_profiles",
    "drugs": "drugs",
    "compliance_rules": "compliance_rules",
    "briefings": "briefings",
    "sales_reps": "sales_reps",
}


@lru_cache
def get_mongo_client() -> AsyncIOMotorClient:
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not configured")
    return AsyncIOMotorClient(uri)


def get_database() -> AsyncIOMotorDatabase:
    db_name = os.getenv("MONGODB_DB") or os.getenv("MONGO_DB_NAME") or "pharmaops"
    return get_mongo_client()[db_name]
