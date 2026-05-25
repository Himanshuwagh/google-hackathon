"""Partner MCP server toolsets for the ADK briefing pipeline.

The deterministic Python tools in this project keep the production payload
shape stable, while these toolsets expose partner MCP servers directly to the
ADK agents for schema discovery, data inspection, and judge-visible partner
integration.
"""

import os

from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioConnectionParams,
    StdioServerParameters,
    StreamableHTTPConnectionParams,
)

from config import (
    ELASTIC_API_KEY,
    ELASTIC_URL,
    MONGO_URI,
)


def _enabled(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _base_enabled() -> bool:
    return _enabled("ENABLE_PARTNER_MCP", True)


def mongodb_mcp_toolset() -> McpToolset | None:
    """Return the official MongoDB MCP server toolset when enabled.

    The server runs read-only by default. The app still writes briefings through
    deterministic tools so the pipeline cannot accidentally mutate arbitrary
    collections through generic MCP operations.
    """
    if not _base_enabled() or not _enabled("ENABLE_MONGODB_MCP", True):
        return None
    if not MONGO_URI:
        return None

    env = {
        **os.environ,
        "MDB_MCP_CONNECTION_STRING": MONGO_URI,
    }
    if _enabled("MONGODB_MCP_READ_ONLY", True):
        env["MDB_MCP_READ_ONLY"] = "true"

    args = ["-y", "mongodb-mcp-server"]
    if _enabled("MONGODB_MCP_READ_ONLY", True):
        args.append("--readOnly")

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=os.getenv("MONGODB_MCP_COMMAND", "npx"),
                args=args,
                env=env,
            ),
            timeout=float(os.getenv("MONGODB_MCP_TIMEOUT", "15")),
        ),
        tool_name_prefix="mongodb",
    )


def elastic_mcp_toolset() -> McpToolset | None:
    """Return an Elastic MCP toolset when a remote MCP endpoint is configured.

    Elastic's current MCP server is distributed primarily as a container or
    streamable-HTTP endpoint. Cloud Run should connect to that endpoint instead
    of trying to start Docker inside the app container.
    """
    if not _base_enabled() or not _enabled("ENABLE_ELASTIC_MCP", False):
        return None

    mcp_url = os.getenv("ELASTIC_MCP_URL")
    if not mcp_url:
        return None

    headers: dict[str, str] = {}
    auth_header = os.getenv("ELASTIC_MCP_AUTH_HEADER")
    if auth_header:
        headers["Authorization"] = auth_header
    elif ELASTIC_API_KEY:
        headers["Authorization"] = f"ApiKey {ELASTIC_API_KEY}"

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=mcp_url,
            headers=headers or None,
            timeout=float(os.getenv("ELASTIC_MCP_TIMEOUT", "15")),
        ),
        tool_name_prefix="elastic",
    )


def partner_mcp_toolsets(*, include_elastic: bool = False) -> list[McpToolset]:
    """Build the MCP toolset list used by ADK LlmAgents."""
    toolsets = [toolset for toolset in [mongodb_mcp_toolset()] if toolset is not None]
    if include_elastic:
        elastic = elastic_mcp_toolset()
        if elastic is not None:
            toolsets.append(elastic)
    return toolsets


def partner_mcp_status() -> dict:
    """Non-secret status for health checks and judge-facing diagnostics."""
    return {
        "enabled": _base_enabled(),
        "mongodb": {
            "enabled": _base_enabled() and _enabled("ENABLE_MONGODB_MCP", True),
            "server": "mongodb-mcp-server",
            "transport": "stdio",
            "read_only": _enabled("MONGODB_MCP_READ_ONLY", True),
            "configured": bool(MONGO_URI),
        },
        "elastic": {
            "enabled": _base_enabled() and _enabled("ENABLE_ELASTIC_MCP", False),
            "server": "Elastic MCP streamable HTTP endpoint",
            "transport": "streamable-http",
            "configured": bool(os.getenv("ELASTIC_MCP_URL") or ELASTIC_URL),
        },
    }
