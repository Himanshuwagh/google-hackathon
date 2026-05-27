"""Smoke tests for MongoDB MCP runtime wiring."""

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.agent_runner import _build_tool_trace
from services.meeting_service import _generation_update_statuses
from tools import mcp_mongo_tools
from tools import mongo_mcp_client
from tools.mongo_mcp_client import (
    MongoMcpConfig,
    MongoMcpError,
    MongoMcpRuntime,
    build_mongodb_mcp_config,
    reset_active_mongodb_mcp,
    set_active_mongodb_mcp,
)
from mcp.types import CallToolResult, TextContent


def _test_mcp_config(**overrides):
    values = {
        "command": "mongodb-mcp-server",
        "args": ["--readOnly"],
        "env": {},
        "database": "pharma_ops",
        "timeout_seconds": 0.2,
        "query_timeout_seconds": 0.05,
        "read_only": True,
        "configured": True,
        "enabled": True,
    }
    values.update(overrides)
    return MongoMcpConfig(**values)


class FakeStdioContext:
    should_fail = False

    async def __aenter__(self):
        if self.should_fail:
            raise OSError("stdio unavailable")
        return "read", "write"

    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakeClientSession:
    tools = [SimpleNamespace(name="find", inputSchema={})]
    calls = []

    def __init__(self, *args, **kwargs):
        del args, kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def initialize(self):
        return SimpleNamespace(serverInfo=SimpleNamespace(version="1.10.0"))

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text='{"documents": [{"_id": "mtg_preflight"}]}',
                )
            ]
        )


def _with_patched_mcp(session_cls, stdio_factory):
    class Patch:
        def __enter__(self):
            self.original_session = mongo_mcp_client.ClientSession
            self.original_stdio = mongo_mcp_client.stdio_client
            mongo_mcp_client.ClientSession = session_cls
            mongo_mcp_client.stdio_client = stdio_factory

        def __exit__(self, exc_type, exc, tb):
            mongo_mcp_client.ClientSession = self.original_session
            mongo_mcp_client.stdio_client = self.original_stdio

    return Patch()


class FakeMongoMcp:
    def __init__(self):
        self.documents = {
            "meetings": [
                {
                    "_id": "multi_meeting",
                    "rep_id": "rep_1",
                    "hcp_id": "hcp_1",
                    "drug_ids": ["drug_a", "drug_b"],
                    "detailing_sequence": ["drug_b", "drug_a"],
                }
            ],
            "sales_reps": [{"_id": "rep_1", "name": "Rep One"}],
            "hcp_profiles": [{"_id": "hcp_1", "name": "Dr. One"}],
            "drugs": [
                {"_id": "drug_a", "brand_name": "Drug A"},
                {"_id": "drug_b", "brand_name": "Drug B"},
            ],
            "compliance_rules": [
                {"_id": "rule_1", "rule_id": "rule_1", "severity": "blocker"}
            ],
        }

    async def find_one(self, collection, query):
        for document in self.documents[collection]:
            if all(document.get(key) == value for key, value in query.items()):
                return document
        return None

    async def find(self, collection, query, limit=10):
        if "_id" in query and isinstance(query["_id"], dict) and "$in" in query["_id"]:
            ids = set(query["_id"]["$in"])
            return [doc for doc in self.documents[collection] if doc.get("_id") in ids][:limit]
        if not query:
            return self.documents[collection][:limit]
        return [
            doc
            for doc in self.documents[collection]
            if all(doc.get(key) == value for key, value in query.items())
        ][:limit]


def test_mongodb_mcp_config_defaults_to_read_only_binary():
    original = dict(os.environ)
    try:
        os.environ["ENABLE_PARTNER_MCP"] = "true"
        os.environ["ENABLE_MONGODB_MCP"] = "true"
        os.environ["MONGODB_MCP_READ_ONLY"] = "true"
        os.environ["MDB_MCP_CONNECTION_STRING"] = "mongodb://example.invalid/pharma_ops"
        config = build_mongodb_mcp_config()
    finally:
        os.environ.clear()
        os.environ.update(original)

    assert config.enabled is True
    assert config.configured is True
    assert config.read_only is True
    assert config.command == "mongodb-mcp-server"
    assert "--readOnly" in config.args
    assert config.env["MDB_MCP_CONNECTION_STRING"] == "mongodb://example.invalid/pharma_ops"
    assert config.env["MDB_MCP_READ_ONLY"] == "true"
    assert config.env["MDB_MCP_MAX_TIME_M_S"] == "5000"


async def _successful_preflight():
    events = []
    FakeClientSession.calls = []
    FakeClientSession.tools = [SimpleNamespace(name="find", inputSchema={})]
    with _with_patched_mcp(FakeClientSession, lambda server: FakeStdioContext()):
        async with MongoMcpRuntime(
            config=_test_mcp_config(),
            trace_callback=events.append,
        ) as runtime:
            return {
                "server_version": runtime.server_version,
                "tools_count": runtime.tools_count,
                "events": events,
                "calls": list(FakeClientSession.calls),
            }


def test_mcp_preflight_initializes_tools_and_runs_bounded_find():
    result = asyncio.run(_successful_preflight())

    assert result["server_version"] == "1.10.0"
    assert result["tools_count"] == 1
    assert result["calls"][0][0] == "find"
    assert result["calls"][0][1]["collection"] == "meetings"
    assert result["calls"][0][1]["limit"] == 1
    assert any(event["tag"] == "MCP_CHECK" and event["phase"] == "completed" for event in result["events"])


async def _failing_preflight(*, tools=None, stdio_failure=False):
    events = []
    FakeClientSession.tools = tools or [SimpleNamespace(name="find", inputSchema={})]
    FakeStdioContext.should_fail = stdio_failure
    try:
        with _with_patched_mcp(FakeClientSession, lambda server: FakeStdioContext()):
            runtime = MongoMcpRuntime(config=_test_mcp_config(), trace_callback=events.append)
            await runtime.start()
    except MongoMcpError as exc:
        return str(exc), events
    finally:
        FakeStdioContext.should_fail = False
    raise AssertionError("Expected MongoMcpError")


def test_mcp_preflight_startup_failure_fails_fast():
    error, events = asyncio.run(_failing_preflight(stdio_failure=True))

    assert "stdio unavailable" in error
    assert any(event["tag"] == "MCP_CHECK" and event["phase"] == "failed" for event in events)


def test_mcp_preflight_requires_find_tool():
    error, events = asyncio.run(
        _failing_preflight(tools=[SimpleNamespace(name="aggregate", inputSchema={})])
    )

    assert "'find' tool is unavailable" in error
    assert any(event["tag"] == "MCP_CHECK" and event["phase"] == "failed" for event in events)


async def _timed_out_query():
    events = []

    class SlowSession:
        async def call_tool(self, name, arguments):
            del name, arguments
            await asyncio.sleep(0.2)

    runtime = MongoMcpRuntime(
        config=_test_mcp_config(query_timeout_seconds=0.01),
        trace_callback=events.append,
    )
    runtime._session = SlowSession()
    runtime.tool_schemas = {"find": {}}
    try:
        await runtime.find("meetings", {}, limit=1)
    except TimeoutError:
        return events
    raise AssertionError("Expected TimeoutError")


def test_mcp_query_timeout_emits_failed_trace():
    events = asyncio.run(_timed_out_query())

    assert any(event["tag"] == "MCP_QUERY" and event["phase"] == "failed" for event in events)


def test_tool_trace_tracks_mongodb_mcp_failure():
    trace = _build_tool_trace(
        "error",
        [
            {
                "tag": "MCP_CHECK",
                "step": "MongoDBMCP",
                "phase": "started",
                "recorded_at": "2026-05-26T00:00:00+00:00",
            },
            {
                "tag": "MCP_CHECK",
                "step": "MongoDBMCP",
                "phase": "failed",
                "recorded_at": "2026-05-26T00:00:01+00:00",
            },
        ],
    )

    assert trace["steps"]["MongoDBMCP"]["status"] == "failed"
    assert trace["status"] == "error"


def test_stale_processing_status_can_be_restarted():
    assert "agent_processing" not in _generation_update_statuses(False)
    assert "agent_processing" in _generation_update_statuses(True)


async def _read_joined_context_with_fake_mcp():
    token = set_active_mongodb_mcp(FakeMongoMcp())
    try:
        meeting = await mcp_mongo_tools.get_meeting("multi_meeting")
        rules = await mcp_mongo_tools.get_compliance_rules()
    finally:
        reset_active_mongodb_mcp(token)
    return meeting, rules


def test_mcp_backed_meeting_read_preserves_joined_shape():
    meeting, rules = asyncio.run(_read_joined_context_with_fake_mcp())

    assert meeting["status"] == "found"
    assert meeting["drug_ids"] == ["drug_b", "drug_a"]
    assert [drug["_id"] for drug in meeting["drugs"]] == ["drug_b", "drug_a"]
    assert meeting["rep"]["name"] == "Rep One"
    assert rules["count"] == 1


if __name__ == "__main__":
    test_mongodb_mcp_config_defaults_to_read_only_binary()
    test_mcp_preflight_initializes_tools_and_runs_bounded_find()
    test_mcp_preflight_startup_failure_fails_fast()
    test_mcp_preflight_requires_find_tool()
    test_mcp_query_timeout_emits_failed_trace()
    test_tool_trace_tracks_mongodb_mcp_failure()
    test_stale_processing_status_can_be_restarted()
    test_mcp_backed_meeting_read_preserves_joined_shape()
    print("MongoDB MCP runtime tests passed.")
