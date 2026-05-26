"""
config.py — Centralised Configuration
Loads all environment variables and connection strings from .env

MCP Server Architecture:
  - MongoDB reads use the official MongoDB MCP server (npm package)
  - MongoDB MCP is spawned once per briefing run as a stdio subprocess
  - Connection strings are passed as environment variables to the MCP processes
  - Controlled writes use deterministic PyMongo application tools
"""

import os
from pathlib import Path
from dotenv import load_dotenv

AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv()

# ── MongoDB Atlas ──────────────────────────────────────────────
# Used by: MCP server (mongodb-mcp-server) for runtime reads
#          pymongo for controlled writes and initial data seeding
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://<user>:<pass>@cluster.mongodb.net/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "pharma_ops")

# ── Elasticsearch ──────────────────────────────────────────────
# Used by: elasticsearch-py at runtime and for initial index seeding
# Supports either ELASTIC_CLOUD_ID (Elastic Cloud) or ELASTIC_URL (self-hosted)
ELASTIC_CLOUD_ID = os.getenv("ELASTIC_CLOUD_ID", "")
ELASTIC_URL = os.getenv("ELASTIC_URL", "")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", "")

# Three separate indices for different document types (BM25 text search)
ELASTIC_IDX_COMPANY_DOCS = os.getenv("ELASTIC_IDX_COMPANY_DOCS", "idx_company_docs")
ELASTIC_IDX_CRM_MEMORY = os.getenv("ELASTIC_IDX_CRM_MEMORY", "idx_crm_memory")
ELASTIC_IDX_COMPETITIVE_INTEL = os.getenv("ELASTIC_IDX_COMPETITIVE_INTEL", "idx_competitive_intel")

# ── Google Cloud / Gemini ──────────────────────────────────────
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "")
GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION", "us-central1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# ── Google APIs (Calendar + Gmail) ─────────────────────────────
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "token.json")

# ── PubMed / ClinicalTrials / OpenFDA (no auth, direct HTTP) ──
PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CLINICALTRIALS_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"

# ── Agent Settings ─────────────────────────────────────────────
MAX_COMPLIANCE_LOOPS = int(os.getenv("MAX_COMPLIANCE_LOOPS", "3"))
BRIEF_STYLE = os.getenv("BRIEF_STYLE", "concise")  # concise | detailed
