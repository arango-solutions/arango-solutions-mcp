"""All-tool tests for the v3 result contract and legacy adapter."""

import os
from datetime import date
from unittest.mock import patch

import pytest

os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")

with patch("arangodb_mcp.arango_connector.ArangoClient"):
    from arangodb_mcp.server import mcp_app

from arangodb_mcp.contracts.v3_result import (
    LEGACY_RESULT_CONTRACT_SUNSET,
    RESULT_CONTRACT_VERSION,
    ResultContractError,
    normalize_result,
)


@pytest.mark.asyncio
async def test_every_registered_tool_dispatches_through_v3_envelope(monkeypatch):
    manager = mcp_app._tool_manager
    original_active = manager._tools
    manager._tools = dict(manager._registered_tools)

    async def successful_call(*_args, **_kwargs):
        return {"value": "ok"}

    metadata_type = type(manager.all_registered_tools()[0].fn_metadata)
    monkeypatch.setattr(metadata_type, "call_fn_with_arg_validation", successful_call)
    try:
        for tool in manager.all_registered_tools():
            result = await manager.call_tool(tool.name, {})
            assert result["contractVersion"] == RESULT_CONTRACT_VERSION
            assert result["meta"]["tool"] == tool.name
            if manager.catalog.get(tool.name).confirmation == "human":
                assert result["status"] == "error"
                assert result["error"]["code"] == "confirmation_not_configured"
            else:
                assert result["status"] == "success"
                assert result["data"] == {"value": "ok"}
                assert result["error"] is None
            assert tool.output_schema["properties"]["contractVersion"]["const"] == "3.0"
        content, structured = await manager.call_tool("list-databases", {}, convert_result=True)
        assert structured["contractVersion"] == "3.0"
        assert "result" not in structured
        assert '"contractVersion": "3.0"' in content[0].text
    finally:
        manager._tools = original_active


@pytest.mark.parametrize(
    "raw,code,message",
    [
        ({"error": "denied", "error_code": 403}, "403", "denied"),
        (
            {"result": {"error": "query failed", "error_code": 1501}},
            "1501",
            "query failed",
        ),
    ],
)
def test_v3_error_envelope_normalizes_existing_error_shapes(raw, code, message):
    result = normalize_result("example-tool", raw)
    assert result["status"] == "error"
    assert result["data"] is None
    assert result["error"]["code"] == code
    assert result["error"]["message"] == message
    assert result["meta"] == {"tool": "example-tool"}


def test_legacy_adapter_is_time_bounded():
    raw = {"legacy": True}
    assert (
        normalize_result(
            "example-tool",
            raw,
            contract="legacy",
            today=LEGACY_RESULT_CONTRACT_SUNSET.replace(year=2026),
        )
        is raw
    )
    with pytest.raises(ResultContractError, match="expired"):
        normalize_result(
            "example-tool",
            raw,
            contract="legacy",
            today=LEGACY_RESULT_CONTRACT_SUNSET,
        )
    assert date(2027, 2, 1) == LEGACY_RESULT_CONTRACT_SUNSET


def test_v3_dispatch_preserves_input_schema_introspection():
    manager = mcp_app._tool_manager
    tools = {tool.name: tool for tool in manager.all_registered_tools()}
    execute = tools["execute-aql-query"]
    create = tools["create-document"]
    assert "aql_query" in execute.parameters["required"]
    assert {"collection_name", "document_data"} <= set(create.parameters["required"])
