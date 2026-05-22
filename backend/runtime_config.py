import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
AGENT_ROOT = BASE_DIR / "pharma-briefing-agent"

ENV_ALIASES = {
    "MONGO_URI": "MONGODB_URI",
    "MONGO_DB_NAME": "MONGODB_DB",
    "GOOGLE_PROJECT_ID": "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_LOCATION": "GOOGLE_CLOUD_LOCATION",
    "GOOGLE_CREDENTIALS_PATH": "GOOGLE_CALENDAR_CREDENTIALS",
    "GEMINI_API_KEY": "GOOGLE_API_KEY",
}


def configure_environment() -> None:
    load_dotenv(AGENT_ROOT / ".env")
    load_dotenv(BASE_DIR / ".env", override=False)
    load_dotenv(BASE_DIR / "backend" / ".env", override=False)

    for source_name, target_name in ENV_ALIASES.items():
        if os.getenv(source_name) and not os.getenv(target_name):
            os.environ[target_name] = os.environ[source_name]
        if os.getenv(target_name) and not os.getenv(source_name):
            os.environ[source_name] = os.environ[target_name]


def validate_runtime_config() -> dict[str, str]:
    configure_environment()

    missing = []
    if not os.getenv("MONGO_URI") and not os.getenv("MONGODB_URI"):
        missing.append("MONGO_URI or MONGODB_URI")
    if not os.getenv("MONGO_DB_NAME") and not os.getenv("MONGODB_DB"):
        missing.append("MONGO_DB_NAME or MONGODB_DB")

    has_api_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    has_vertex_project = bool(os.getenv("GOOGLE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT"))
    has_credentials_path = bool(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or os.getenv("GOOGLE_CREDENTIALS_PATH")
        or os.getenv("GOOGLE_CALENDAR_CREDENTIALS")
    )
    if not has_api_key and not (has_vertex_project and has_credentials_path):
        missing.append("GOOGLE_API_KEY/GEMINI_API_KEY or Vertex project + credentials path")

    if not AGENT_ROOT.exists():
        missing.append(f"agent directory at {AGENT_ROOT}")

    if missing:
        raise RuntimeError("Missing required runtime configuration: " + ", ".join(missing))

    return {
        "mongo_db": os.getenv("MONGO_DB_NAME") or os.getenv("MONGODB_DB") or "",
        "agent_root": str(AGENT_ROOT),
        "google_auth": "api_key" if has_api_key else "vertex",
    }
