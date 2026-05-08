"""Tests for the ``/healthz`` ASGI app and the JSON log formatter.

The health app and JSON log formatter both live in ``main.py``. We exercise
them directly via a small in-process ASGI driver (no uvicorn / no real
ArangoDB connection required). ``arango_connector.health_check`` is mocked
so we can deterministically test both the healthy and unhealthy branches.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

# Required env so config / server imports don't fail at collection time.
os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")
os.environ.setdefault("ARANGO_DEFAULT_DB_NAME", "_system")

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Patch ArangoClient before main → server → arango_connector instantiates it.
with patch("arango_connector.ArangoClient"):
    import main  # noqa: E402

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
# /healthz tests
# ---------------------------------------------------------------------------


def test_healthz_ok_when_connection_healthy():
    # ``server_version`` is a read-only @property backed by ``_server_version``;
    # poke the backing attribute directly to override.
    original_version = main.arango_connector._server_version
    main.arango_connector._server_version = "3.12.5"
    try:
        with patch.object(main.arango_connector, "health_check", return_value=True):
            response = asyncio.run(_drive(health_app))
    finally:
        main.arango_connector._server_version = original_version

    assert response["status"] == 200
    assert (b"content-type", b"application/json") in response["headers"]
    payload = json.loads(response["body"])
    assert payload["status"] == "ok"
    assert payload["server_version"] == "3.12.5"


def test_healthz_503_when_connection_unhealthy():
    with patch.object(main.arango_connector, "health_check", return_value=False):
        response = asyncio.run(_drive(health_app))

    assert response["status"] == 503
    payload = json.loads(response["body"])
    assert payload == {"status": "unhealthy"}


def test_healthz_405_for_non_get():
    # health_check should NOT even be called for the wrong method.
    with patch.object(main.arango_connector, "health_check", return_value=True) as hc:
        response = asyncio.run(_drive(health_app, method="POST"))

    assert response["status"] == 405
    assert hc.call_count == 0
    assert (b"allow", b"GET") in response["headers"]
    payload = json.loads(response["body"])
    assert "error" in payload


def test_healthz_body_is_valid_json_for_all_branches():
    # Healthy
    with patch.object(main.arango_connector, "health_check", return_value=True):
        ok = asyncio.run(_drive(health_app))
    json.loads(ok["body"])

    # Unhealthy
    with patch.object(main.arango_connector, "health_check", return_value=False):
        bad = asyncio.run(_drive(health_app))
    json.loads(bad["body"])

    # Wrong method
    bad_method = asyncio.run(_drive(health_app, method="DELETE"))
    json.loads(bad_method["body"])


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
