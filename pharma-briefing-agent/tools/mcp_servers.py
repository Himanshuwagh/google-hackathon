"""Partner MCP status helpers for the briefing runtime."""

from __future__ import annotations

import asyncio
import os

from tools.mongo_mcp_client import (
    build_mongodb_mcp_config,
    check_mongodb_mcp_status,
)


def _enabled(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _base_enabled() -> bool:
    return _enabled("ENABLE_PARTNER_MCP", True)


def _mongodb_status() -> dict:
    config = build_mongodb_mcp_config()
    fallback = {
        "enabled": config.enabled,
        "configured": config.configured,
        "connected": False,
        "read_only": config.read_only,
        "server": "mongodb-mcp-server",
        "package": "mongodb-mcp-server@1.10.0",
        "transport": "stdio",
        "server_version": None,
        "tools_count": 0,
        "last_error": None,
    }

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(check_mongodb_mcp_status())

    fallback["last_error"] = "Live MCP status check skipped inside running event loop"
    return fallback


def partner_mcp_toolsets() -> list:
    """Deprecated compatibility shim.

    The briefing pipeline now uses a preflighted deterministic MCP wrapper
    instead of attaching raw MCP toolsets directly to LLM agents.
    """
    return []


def partner_mcp_status() -> dict:
    """Non-secret status for health checks and judge-facing diagnostics."""
    return {
        "enabled": _base_enabled(),
        "mongodb": _mongodb_status(),
    }
