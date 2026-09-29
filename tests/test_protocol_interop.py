"""Pinned strict and legacy MCP Streamable HTTP interoperability flows."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.testclient import TestClient

from arangodb_mcp.middleware.protocol import ProtocolMetadataMiddleware, ProtocolMode
from arangodb_mcp.protocol_compat import (
    COMPATIBILITY_SUNSET,
    MCP_2026_VERSION,
    enable_mcp_2026_negotiation,
)


def _probe_app(mode: ProtocolMode):
    enable_mcp_2026_negotiation()
    probe = FastMCP("interop-probe", stateless_http=True, json_response=True)

    @probe.tool()
    def echo(value: str) -> dict[str, str]:
        return {"value": value}

    return ProtocolMetadataMiddleware(probe.streamable_http_app(), mode=mode)


def test_protocol_bridge_is_current_and_time_bounded():
    bridge_required = enable_mcp_2026_negotiation()

    assert MCP_2026_VERSION == "2026-07-28"
    if bridge_required:
        assert date.today() < date.fromisoformat(COMPATIBILITY_SUNSET)


def _strict_post(
    client: TestClient,
    method: str,
    params: dict[str, Any],
    *,
    request_id: int,
    name: str | None = None,
):
    headers = {
        "host": "localhost:8000",
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    params = {
        **params,
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        headers=headers,
    )


def test_strict_2026_stateless_initialize_list_and_call_flow():
    with TestClient(_probe_app("strict")) as client:
        initialized = _strict_post(
            client,
            "initialize",
            {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "pinned-test-client", "version": "1.0"},
            },
            request_id=1,
        )
        listed = _strict_post(client, "tools/list", {}, request_id=2)
        called = _strict_post(
            client,
            "tools/call",
            {"name": "echo", "arguments": {"value": "ok"}},
            request_id=3,
            name="echo",
        )

    assert initialized.status_code == 200
    assert initialized.json()["result"]["protocolVersion"] == "2026-07-28"
    assert "mcp-session-id" not in initialized.headers
    list_result = listed.json()["result"]
    assert [tool["name"] for tool in list_result["tools"]] == ["echo"]
    assert list_result["resultType"] == "complete"
    assert list_result["ttlMs"] == 300_000
    assert list_result["cacheScope"] == "public"
    assert called.json()["result"]["isError"] is False
    assert '"value": "ok"' in called.json()["result"]["content"][0]["text"]


def test_auto_mode_retains_headerless_2025_client_compatibility():
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "legacy-client", "version": "1.0"},
        },
    }
    with TestClient(_probe_app("auto")) as client:
        response = client.post(
            "/mcp",
            json=body,
            headers={
                "host": "localhost:8000",
                "accept": "application/json, text/event-stream",
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["protocolVersion"] == "2025-11-25"


def test_explicit_legacy_mode_ignores_partial_routing_headers():
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "legacy-client", "version": "1.0"},
        },
    }
    with TestClient(_probe_app("legacy")) as client:
        response = client.post(
            "/mcp",
            json=body,
            headers={
                "host": "localhost:8000",
                "accept": "application/json, text/event-stream",
                "mcp-method": "intentionally-wrong",
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["protocolVersion"] == "2025-11-25"
