"""Read-only MongoDB MCP runtime for briefing generation.

This module owns the official MongoDB MCP stdio process for one pipeline run.
Agent tools use the active runtime through a context variable so MCP startup is
preflighted once and deterministic read tools do not repeatedly create raw
``McpToolset`` sessions inside LLM steps.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import AsyncExitStack
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult

from config import MONGO_DB_NAME, MONGO_URI


logger = logging.getLogger("pharmaops.mongo_mcp_client")
MONGODB_MCP_PACKAGE = "mongodb-mcp-server@1.10.0"
MONGODB_MCP_SERVER = "mongodb-mcp-server"
DEFAULT_MCP_TIMEOUT_SECONDS = 15.0
DEFAULT_MCP_QUERY_TIMEOUT_SECONDS = 8.0
DEFAULT_MCP_MAX_TIME_MS = "5000"

TraceCallback = Callable[[dict[str, Any]], None]
_active_runtime: ContextVar["MongoMcpRuntime | None"] = ContextVar(
    "active_mongodb_mcp_runtime",
    default=None,
)


class MongoMcpError(RuntimeError):
    """Raised when MongoDB MCP is required but unavailable."""


def _enabled(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def mongodb_mcp_enabled() -> bool:
    return _enabled("ENABLE_PARTNER_MCP", True) and _enabled("ENABLE_MONGODB_MCP", True)


def mongodb_mcp_read_only() -> bool:
    return _enabled("MONGODB_MCP_READ_ONLY", True)


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _is_configured_connection_string(value: str | None) -> bool:
    return bool(value and "<user>" not in value and "<pass>" not in value)


@dataclass(frozen=True)
class MongoMcpConfig:
    command: str
    args: list[str]
    env: dict[str, str]
    database: str
    timeout_seconds: float
    query_timeout_seconds: float
    read_only: bool
    configured: bool
    enabled: bool


def build_mongodb_mcp_config() -> MongoMcpConfig:
    """Build a non-secret MongoDB MCP process configuration."""
    enabled = mongodb_mcp_enabled()
    read_only = mongodb_mcp_read_only()
    timeout_seconds = _float_env("MONGODB_MCP_TIMEOUT", DEFAULT_MCP_TIMEOUT_SECONDS)
    query_timeout_seconds = _float_env(
        "MONGODB_MCP_QUERY_TIMEOUT",
        DEFAULT_MCP_QUERY_TIMEOUT_SECONDS,
    )
    connection_string = os.getenv("MDB_MCP_CONNECTION_STRING") or os.getenv("MONGO_URI") or MONGO_URI
    database = os.getenv("MONGODB_DB") or os.getenv("MONGO_DB_NAME") or MONGO_DB_NAME

    env = {
        **os.environ,
        "MDB_MCP_CONNECTION_STRING": connection_string,
        "MDB_MCP_READ_ONLY": "true" if read_only else "false",
        "MDB_MCP_MAX_TIME_M_S": os.getenv("MDB_MCP_MAX_TIME_M_S", DEFAULT_MCP_MAX_TIME_MS),
    }

    args: list[str] = []
    if read_only:
        args.append("--readOnly")

    return MongoMcpConfig(
        command=os.getenv("MONGODB_MCP_COMMAND", MONGODB_MCP_SERVER),
        args=args,
        env=env,
        database=database,
        timeout_seconds=timeout_seconds,
        query_timeout_seconds=query_timeout_seconds,
        read_only=read_only,
        configured=_is_configured_connection_string(connection_string),
        enabled=enabled,
    )


def _emit(trace_callback: TraceCallback | None, payload: dict[str, Any]) -> None:
    if not trace_callback:
        return
    try:
        trace_callback(payload)
    except Exception:
        return


def _schema_properties(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    return properties if isinstance(properties, dict) else {}


def _as_tool_arg(properties: dict[str, Any], candidates: list[str], value: Any) -> tuple[str, Any] | None:
    for name in candidates:
        if name in properties:
            schema = properties.get(name) if isinstance(properties.get(name), dict) else {}
            if schema.get("type") == "string" and not isinstance(value, str):
                return name, json.dumps(value)
            return name, value
    return None


def _parse_json_text(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if not match:
        return text
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return text


def _result_payload(result: CallToolResult) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured

    text_parts = [
        part.text
        for part in getattr(result, "content", []) or []
        if getattr(part, "type", None) == "text" and getattr(part, "text", None)
    ]
    if not text_parts:
        return None
    if len(text_parts) == 1:
        return _parse_json_text(text_parts[0])
    return [_parse_json_text(part) for part in text_parts]


def _extract_documents(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            return payload
        documents: list[dict[str, Any]] = []
        for item in payload:
            documents.extend(_extract_documents(item))
        return documents

    if not isinstance(payload, dict):
        return []

    for key in ("documents", "results", "result", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_documents(value)
            if nested:
                return nested

    # Some MCP responses are {"content": [{"...doc..."}]}.
    for value in payload.values():
        nested = _extract_documents(value)
        if nested:
            return nested

    if "_id" in payload:
        return [payload]
    return []


def _tool_names(tools_result: Any) -> list[str]:
    tools = getattr(tools_result, "tools", None) or []
    return [getattr(tool, "name", "") for tool in tools if getattr(tool, "name", "")]


class MongoMcpRuntime:
    """Owns one MongoDB MCP stdio session."""

    def __init__(
        self,
        *,
        config: MongoMcpConfig | None = None,
        trace_callback: TraceCallback | None = None,
    ) -> None:
        self.config = config or build_mongodb_mcp_config()
        self.trace_callback = trace_callback
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self.tool_schemas: dict[str, dict[str, Any]] = {}
        self.tools_count = 0
        self.server_version: str | None = None

    async def __aenter__(self) -> "MongoMcpRuntime":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self.close()
        except Exception as close_error:
            logger.warning("MongoDB MCP cleanup failed: %s", close_error)

    async def start(self) -> None:
        if not self.config.enabled:
            raise MongoMcpError("MongoDB MCP is disabled by runtime configuration")
        if not self.config.configured:
            raise MongoMcpError("MongoDB MCP is missing MDB_MCP_CONNECTION_STRING/MONGO_URI")

        _emit(
            self.trace_callback,
            {
                "tag": "MCP_CHECK",
                "step": "MongoDBMCP",
                "phase": "started",
                "message": "MongoDB MCP preflight started",
            },
        )

        try:
            self._stack = AsyncExitStack()
            server = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
            )
            async with asyncio.timeout(self.config.timeout_seconds):
                read_stream, write_stream = await self._stack.enter_async_context(
                    stdio_client(server)
                )
            self._session = await self._stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=self.config.query_timeout_seconds),
                )
            )
            init_result = await asyncio.wait_for(
                self._session.initialize(),
                timeout=self.config.timeout_seconds,
            )
            server_info = getattr(init_result, "serverInfo", None)
            self.server_version = getattr(server_info, "version", None)

            tools_result = await asyncio.wait_for(
                self._session.list_tools(),
                timeout=self.config.timeout_seconds,
            )
            tools = getattr(tools_result, "tools", None) or []
            self.tools_count = len(tools)
            self.tool_schemas = {
                tool.name: (getattr(tool, "inputSchema", None) or {})
                for tool in tools
                if getattr(tool, "name", None)
            }
            if "find" not in self.tool_schemas:
                raise MongoMcpError("MongoDB MCP 'find' tool is unavailable")

            await self.find("meetings", {}, limit=1)
        except Exception as exc:
            try:
                await self.close()
            except Exception as close_error:
                logger.warning("MongoDB MCP cleanup failed after startup error: %s", close_error)
            message = f"MongoDB MCP preflight failed: {exc}"
            _emit(
                self.trace_callback,
                {
                    "tag": "MCP_CHECK",
                    "step": "MongoDBMCP",
                    "phase": "failed",
                    "level": "error",
                    "message": message,
                },
            )
            if isinstance(exc, MongoMcpError):
                raise
            raise MongoMcpError(message) from exc

        _emit(
            self.trace_callback,
            {
                "tag": "MCP_CHECK",
                "step": "MongoDBMCP",
                "phase": "completed",
                "level": "success",
                "message": "MongoDB MCP preflight completed",
                "tools_count": self.tools_count,
            },
        )

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._session = None
        self._stack = None

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise MongoMcpError("MongoDB MCP runtime is not active")
        return self._session

    def _build_find_args(
        self,
        collection: str,
        query: dict[str, Any],
        *,
        limit: int,
        projection: dict[str, Any] | None = None,
        sort: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        properties = _schema_properties(self.tool_schemas.get("find"))
        args: dict[str, Any] = {}
        for candidates, value in (
            (["database", "databaseName", "db", "dbName"], self.config.database),
            (["collection", "collectionName"], collection),
            (["filter", "query"], query),
            (["limit"], limit),
            (["projection", "project"], projection),
            (["sort"], sort),
        ):
            if value is None:
                continue
            item = _as_tool_arg(properties, candidates, value)
            if item:
                args[item[0]] = item[1]

        # Fallback for tests and future-compatible schemas.
        args.setdefault("database", self.config.database)
        args.setdefault("collection", collection)
        args.setdefault("filter", query)
        args.setdefault("limit", limit)
        return args

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        session = self._require_session()
        result = await asyncio.wait_for(
            session.call_tool(name, arguments),
            timeout=self.config.query_timeout_seconds,
        )
        if getattr(result, "isError", False):
            raise MongoMcpError(f"MongoDB MCP tool {name} returned an error: {_result_payload(result)}")
        return _result_payload(result)

    async def find(
        self,
        collection: str,
        query: dict[str, Any],
        *,
        limit: int = 10,
        projection: dict[str, Any] | None = None,
        sort: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        args = self._build_find_args(
            collection,
            query,
            limit=limit,
            projection=projection,
            sort=sort,
        )
        _emit(
            self.trace_callback,
            {
                "tag": "MCP_QUERY",
                "step": "MongoDBMCP",
                "phase": "started",
                "message": f"MongoDB MCP find started for {collection}",
                "collection": collection,
            },
        )
        try:
            payload = await self.call_tool("find", args)
        except Exception as exc:
            _emit(
                self.trace_callback,
                {
                    "tag": "MCP_QUERY",
                    "step": "MongoDBMCP",
                    "phase": "failed",
                    "level": "error",
                    "message": f"MongoDB MCP find failed for {collection}: {exc}",
                    "collection": collection,
                },
            )
            raise

        documents = _extract_documents(payload)
        _emit(
            self.trace_callback,
            {
                "tag": "MCP_QUERY",
                "step": "MongoDBMCP",
                "phase": "completed",
                "level": "success",
                "message": f"MongoDB MCP find completed for {collection}",
                "collection": collection,
                "count": len(documents),
            },
        )
        return documents

    async def find_one(self, collection: str, query: dict[str, Any]) -> dict[str, Any] | None:
        documents = await self.find(collection, query, limit=1)
        return documents[0] if documents else None


def set_active_mongodb_mcp(runtime: MongoMcpRuntime) -> Token:
    return _active_runtime.set(runtime)


def reset_active_mongodb_mcp(token: Token) -> None:
    _active_runtime.reset(token)


def get_active_mongodb_mcp() -> MongoMcpRuntime:
    runtime = _active_runtime.get()
    if runtime is None:
        raise MongoMcpError("MongoDB MCP runtime has not been preflighted for this run")
    return runtime


async def check_mongodb_mcp_status() -> dict[str, Any]:
    """Return live MongoDB MCP status for `/agent-runtime`."""
    config = build_mongodb_mcp_config()
    status: dict[str, Any] = {
        "enabled": config.enabled,
        "configured": config.configured,
        "connected": False,
        "read_only": config.read_only,
        "server": MONGODB_MCP_SERVER,
        "package": MONGODB_MCP_PACKAGE,
        "transport": "stdio",
        "server_version": None,
        "tools_count": 0,
        "last_error": None,
    }
    if not config.enabled or not config.configured:
        return status

    try:
        async with MongoMcpRuntime(config=config) as runtime:
            status["connected"] = True
            status["server_version"] = runtime.server_version
            status["tools_count"] = runtime.tools_count
    except Exception as exc:
        status["last_error"] = str(exc)
    return status
