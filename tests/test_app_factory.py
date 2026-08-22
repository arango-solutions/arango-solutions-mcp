"""Composition tests for the standalone ASGI application factory."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from prometheus_client import CollectorRegistry

from arangodb_mcp import main
from arangodb_mcp.asgi.app_factory import create_http_app
from arangodb_mcp.config import settings
from arangodb_mcp.observability.metrics import configure_metrics_registry, observe_tool
from arangodb_mcp.oidc import OIDCConfig, OIDCValidator
from arangodb_mcp.policy.credentials import StaticCredentialProvider


async def _drive(
    app,
    *,
    path: str,
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
    body: bytes = b"",
):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "server": ("localhost", 8000),
        "client": ("testclient", 12345),
    }
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    response = {"status": None, "headers": [], "body": b""}

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
            response["headers"] = message.get("headers", [])
        elif message["type"] == "http.response.body":
            response["body"] += message.get("body", b"")

    await app(scope, receive, send)
    return response


def _headers(response) -> dict[bytes, bytes]:
    return dict(response["headers"])


def test_factory_supports_legacy_sse_and_rejects_unknown_transport():
    assert callable(create_http_app("sse", "test-token"))
    with pytest.raises(ValueError, match="Unsupported HTTP transport"):
        create_http_app("websocket", "test-token")


def test_cli_retains_stdio_transport(monkeypatch):
    run = Mock()
    monkeypatch.setattr(settings.server, "mcp_transport", "stdio")
    monkeypatch.setattr(main.mcp_app, "run", run)

    main.run_server_cli()

    run.assert_called_once_with(transport="stdio")


@pytest.mark.asyncio
async def test_livez_bypasses_auth_and_receives_request_id():
    app = create_http_app("streamable-http", "test-token")
    response = await _drive(
        app,
        path="/livez",
        headers=[(b"x-request-id", b"probe-123")],
    )

    assert response["status"] == 200
    assert json.loads(response["body"]) == {"status": "alive"}
    assert _headers(response)[b"x-request-id"] == b"probe-123"


@pytest.mark.asyncio
async def test_http_propagates_w3c_traceparent_and_serves_bounded_metrics():
    registry = CollectorRegistry()
    configure_metrics_registry(registry)
    observe_tool("list-databases", "read", "success", 0.01)
    app = create_http_app("streamable-http", "test-token")
    incoming = b"00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"

    traced = await _drive(
        app,
        path="/livez",
        headers=[(b"x-request-id", b"trace-test"), (b"traceparent", incoming)],
    )
    response_traceparent = _headers(traced)[b"traceparent"].decode()
    assert response_traceparent.split("-")[1] == incoming.decode().split("-")[1]
    assert _headers(traced)[b"x-request-id"] == b"trace-test"

    scraped = await _drive(app, path="/metrics")
    assert scraped["status"] == 200
    assert (
        b'mcp_tool_calls_total{operation="read",outcome="success",tool="list-databases"} 1.0'
        in scraped["body"]
    )
    assert b"actor=" not in scraped["body"]
    assert b"database=" not in scraped["body"]
    assert b"query=" not in scraped["body"]
    assert b"error_message=" not in scraped["body"]
    label_names = {
        label
        for family in registry.collect()
        for sample in family.samples
        for label in sample.labels
    }
    assert label_names <= {
        "tool",
        "operation",
        "outcome",
        "dependency",
        "scope",
        "limit_class",
        "reason",
        "le",
    }
    assert {"actor", "database", "query", "error_message"}.isdisjoint(label_names)


@pytest.mark.asyncio
async def test_transport_security_precedes_bearer_auth():
    app = create_http_app("streamable-http", "test-token")
    response = await _drive(
        app,
        path="/mcp",
        method="POST",
        headers=[
            (b"host", b"localhost:8000"),
            (b"origin", b"https://attacker.example"),
            (b"content-type", b"application/json"),
        ],
        body=b"{}",
    )

    assert response["status"] == 403
    assert b"x-request-id" in _headers(response)


@pytest.mark.asyncio
async def test_invalid_host_is_rejected_before_mcp_dispatch():
    app = create_http_app("streamable-http", "")
    response = await _drive(
        app,
        path="/mcp",
        method="POST",
        headers=[
            (b"host", b"attacker.example"),
            (b"content-type", b"application/json"),
        ],
        body=b"{}",
    )

    assert response["status"] == 421


@pytest.mark.asyncio
async def test_unsafe_client_request_id_is_replaced():
    app = create_http_app("streamable-http", "test-token")
    response = await _drive(
        app,
        path="/livez",
        headers=[(b"x-request-id", b"contains spaces and controls\n")],
    )

    request_id = _headers(response)[b"x-request-id"]
    assert request_id != b"contains spaces and controls\n"
    assert len(request_id) == 32


@pytest.mark.asyncio
async def test_rfc9728_metadata_is_public_and_names_only_oauth_operation_scopes(monkeypatch):
    config = OIDCConfig(
        issuer="https://issuer.example",
        audience="arangodb-mcp",
        resource="https://mcp.example/mcp",
    )
    provider = StaticCredentialProvider.from_json(
        '{"*":{"username":"scoped","password":"server-secret","databases":["tenant_a"]}}'
    )
    validator = OIDCValidator(config, provider)
    monkeypatch.setattr(settings.identity, "mcp_oidc_issuer", config.issuer)

    app = create_http_app("streamable-http", "", oidc_validator=validator)
    response = await _drive(
        app,
        path="/.well-known/oauth-protected-resource/mcp",
        headers=[(b"host", b"localhost:8000")],
    )

    assert response["status"] == 200
    document = json.loads(response["body"])
    assert document == {
        "resource": "https://mcp.example/mcp",
        "authorization_servers": ["https://issuer.example"],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["mcp:admin", "mcp:read", "mcp:write"],
    }
    assert b"database" not in response["body"]


def test_cli_allows_complete_oidc_configuration_without_legacy_token(monkeypatch):
    run = Mock()
    monkeypatch.setattr(settings.server, "mcp_transport", "streamable-http")
    monkeypatch.setattr(settings.server, "mcp_host", "0.0.0.0")
    monkeypatch.setattr(settings.server, "mcp_auth_token", None)
    monkeypatch.setattr(settings.identity, "mcp_oidc_issuer", "https://issuer.example")
    monkeypatch.setattr(settings.identity, "mcp_oidc_audience", "arangodb-mcp")
    monkeypatch.setattr(settings.identity, "mcp_resource_url", "https://mcp.example/mcp")
    monkeypatch.setattr(
        settings.identity,
        "mcp_arango_credentials_json",
        type(settings.arango.root_password)(
            '{"*":{"username":"scoped","password":"server-secret","databases":["tenant_a"]}}'
        ),
    )
    monkeypatch.setattr(main, "_run_http_transport", run)

    main.run_server_cli()

    run.assert_called_once_with("streamable-http", "0.0.0.0", 8000, "")
