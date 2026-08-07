"""Tests for the probe ASGI app and the JSON log formatter.

The health app and JSON log formatter both live in ``main.py``. We exercise
them directly via a small in-process ASGI driver (no uvicorn / no real
ArangoDB connection required). ``arango_connector.health_check`` is mocked
so we can deterministically test both readiness branches. Setting
``MCP_PROBE_BASE_URL`` runs the probe contract test against a live server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# Required env so config / server imports don't fail at collection time.
os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")
os.environ.setdefault("ARANGO_DEFAULT_DB_NAME", "_system")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Patch ArangoClient before main → server → arango_connector instantiates it.
with patch("arangodb_mcp.arango_connector.ArangoClient"):
    from arangodb_mcp import main  # noqa: E402

health_app = main.health_app
JsonFormatter = main.JsonFormatter


# ---------------------------------------------------------------------------
# Tiny ASGI driver
# ---------------------------------------------------------------------------


async def _drive(app, *, path: str = "/healthz", method: str = "GET") -> dict[str, Any]:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
    }

    sent = asyncio.Event()

    async def receive():
        if sent.is_set():
            return {"type": "http.disconnect"}
        sent.set()
        return {"type": "http.request", "body": b"", "more_body": False}

    response: dict[str, Any] = {"status": None, "headers": [], "body": b""}

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
            response["headers"] = message.get("headers", [])
        elif message["type"] == "http.response.body":
            response["body"] += message.get("body", b"")

    await app(scope, receive, send)
    return response


# ---------------------------------------------------------------------------
# Probe tests
# ---------------------------------------------------------------------------


def test_livez_is_process_only_and_does_not_check_arangodb():
    with patch.object(main.arango_connector, "health_check") as health_check:
        response = asyncio.run(_drive(health_app, path="/livez"))

    assert response["status"] == 200
    assert (b"content-type", b"application/json") in response["headers"]
    assert (b"cache-control", b"no-store") in response["headers"]
    assert json.loads(response["body"]) == {"status": "alive"}
    health_check.assert_not_called()


@pytest.mark.parametrize("path", ["/readyz", "/healthz"])
def test_readiness_503_when_arangodb_unhealthy(path):
    with patch.object(main.arango_connector, "health_check", return_value=False):
        response = asyncio.run(_drive(health_app, path=path))

    assert response["status"] == 503
    payload = json.loads(response["body"])
    assert payload == {"status": "not_ready", "checks": {"arangodb": "unhealthy"}}


@pytest.mark.parametrize("path", ["/livez", "/readyz", "/healthz"])
def test_probes_405_for_non_get(path):
    # health_check should NOT even be called for the wrong method.
    with patch.object(main.arango_connector, "health_check", return_value=True) as hc:
        response = asyncio.run(_drive(health_app, path=path, method="POST"))

    assert response["status"] == 405
    assert hc.call_count == 0
    assert (b"allow", b"GET") in response["headers"]
    payload = json.loads(response["body"])
    assert "error" in payload


def test_readiness_alias_contract_in_process_or_live():
    base_url = os.environ.get("MCP_PROBE_BASE_URL")
    if base_url:
        responses = {}
        for path in ("/livez", "/readyz", "/healthz"):
            with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=3) as response:
                responses[path] = (
                    response.status,
                    dict(response.headers.items()),
                    json.load(response),
                )

        assert responses["/livez"][0] == 200
        assert responses["/livez"][2] == {"status": "alive"}
        assert responses["/readyz"][0] == 200
        assert responses["/readyz"][2]["status"] == "ready"
        assert responses["/healthz"][2] == responses["/readyz"][2]
        assert responses["/healthz"][1]["Deprecation"] == "@1785888000"
        return

    original_version = main.arango_connector._server_version
    main.arango_connector._server_version = "3.12.5"
    try:
        with patch.object(main.arango_connector, "health_check", return_value=True):
            ready = asyncio.run(_drive(health_app, path="/readyz"))
            alias = asyncio.run(_drive(health_app, path="/healthz"))
    finally:
        main.arango_connector._server_version = original_version

    expected = {
        "status": "ready",
        "checks": {"arangodb": "ok"},
        "server_version": "3.12.5",
    }
    assert ready["status"] == 200
    assert json.loads(ready["body"]) == expected
    assert json.loads(alias["body"]) == expected
    assert (b"deprecation", b"@1785888000") in alias["headers"]
    assert (b"link", b'</readyz>; rel="successor-version"') in alias["headers"]


def test_http_server_owns_database_lifecycle():
    server = SimpleNamespace(serve=AsyncMock())
    connect = AsyncMock()
    disconnect = AsyncMock()

    with (
        patch.object(main.arango_connector, "connect", connect),
        patch.object(main.arango_connector, "disconnect", disconnect),
    ):
        asyncio.run(main._serve_http_with_database(server))

    connect.assert_awaited_once_with()
    server.serve.assert_awaited_once_with()
    disconnect.assert_awaited_once_with()


def test_http_server_disconnects_database_when_serve_fails():
    server = SimpleNamespace(serve=AsyncMock(side_effect=RuntimeError("serve failed")))
    disconnect = AsyncMock()

    with (
        patch.object(main.arango_connector, "connect", AsyncMock()),
        patch.object(main.arango_connector, "disconnect", disconnect),
        pytest.raises(RuntimeError, match="serve failed"),
    ):
        asyncio.run(main._serve_http_with_database(server))

    disconnect.assert_awaited_once_with()


# ---------------------------------------------------------------------------
# JsonFormatter tests
# ---------------------------------------------------------------------------


def test_json_formatter_emits_one_line_json_with_expected_keys():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="some.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    rendered = formatter.format(record)
    # One line, no embedded newlines.
    assert "\n" not in rendered

    payload = json.loads(rendered)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "some.logger"
    assert payload["message"] == "hello world"
    assert "ts" in payload
    assert payload["ts"].endswith("Z")
    # Sanity: the formatter should not leak unknown fields.
    assert "exc" not in payload


def test_json_formatter_includes_exception_info():
    formatter = JsonFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="some.logger",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="something went wrong",
        args=(),
        exc_info=exc_info,
    )

    payload = json.loads(formatter.format(record))
    assert payload["level"] == "ERROR"
    assert "exc" in payload
    assert "RuntimeError: boom" in payload["exc"]
