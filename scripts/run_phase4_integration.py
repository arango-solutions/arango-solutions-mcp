#!/usr/bin/env python3
"""Run the containerized OIDC, Prometheus, and OTLP Phase 4 acceptance flow."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPOSE = ROOT / "docker-compose.phase4.yml"
PROTOCOL_VERSION = "2026-07-28"


class HarnessError(RuntimeError):
    """Deterministic acceptance failure."""


def _free_ports(count: int) -> tuple[int, ...]:
    listeners: list[socket.socket] = []
    try:
        for _ in range(count):
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 0))
            listeners.append(listener)
        return tuple(int(listener.getsockname()[1]) for listener in listeners)
    finally:
        for listener in listeners:
            listener.close()


def _run(
    command: list[str],
    *,
    env: dict[str, str],
    timeout: float,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=capture,
        check=True,
        timeout=timeout,
    )


def _json_request(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 5,
) -> tuple[int, dict[str, Any]]:
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode()
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=payload,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            document = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            document = {"raw": raw.decode(errors="replace")}
        return exc.code, document


def _strict_mcp_post(
    base_url: str,
    token: str,
    *,
    method: str,
    params: dict[str, Any],
    request_id: int,
    name: str | None = None,
) -> tuple[int, dict[str, Any]]:
    strict_params = {
        **params,
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "MCP-Method": method,
    }
    if name is not None:
        headers["MCP-Name"] = name
    return _json_request(
        f"{base_url}/mcp",
        method="POST",
        headers=headers,
        body={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": strict_params,
        },
    )


def _wait_for(
    description: str,
    assertion,
    *,
    deadline: float,
    interval: float = 1,
) -> Any:
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = assertion()
            if value:
                return value
        except Exception as exc:  # noqa: BLE001 - retain final probe cause
            last_error = exc
        time.sleep(interval)
    suffix = f": {last_error}" if last_error is not None else ""
    raise HarnessError(f"Timed out waiting for {description}{suffix}")


def _prometheus_value(base_url: str, query: str) -> float:
    encoded = urllib.parse.urlencode({"query": query})
    status, document = _json_request(f"{base_url}/api/v1/query?{encoded}")
    if status != 200 or document.get("status") != "success":
        return 0
    results = document.get("data", {}).get("result", [])
    if not results:
        return 0
    return float(results[0]["value"][1])


def run_harness(args: argparse.Namespace) -> None:
    compose_file = Path(args.compose_file).resolve()
    if not compose_file.is_file():
        raise HarnessError(f"Compose file not found: {compose_file}")

    mcp_port, idp_port, prometheus_port, otel_health_port = _free_ports(4)
    env = os.environ.copy()
    env.update(
        {
            "PHASE4_ARANGO_PASSWORD": secrets.token_urlsafe(24),
            "PHASE4_MCP_PORT": str(mcp_port),
            "PHASE4_IDP_PORT": str(idp_port),
            "PHASE4_PROMETHEUS_PORT": str(prometheus_port),
            "PHASE4_OTEL_HEALTH_PORT": str(otel_health_port),
        }
    )
    project = f"arangodb-mcp-phase4-{os.getpid()}-{secrets.token_hex(3)}"
    compose = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--file",
        str(compose_file),
    ]
    timeout = float(args.timeout)
    deadline = time.monotonic() + timeout
    failed = False

    try:
        _run(["docker", "info"], env=env, timeout=15, capture=True)
        _run(["docker", "compose", "version"], env=env, timeout=15, capture=True)
        _run(
            [*compose, "up", "--build", "--detach", "--wait", "--wait-timeout", str(int(timeout))],
            env=env,
            timeout=timeout,
        )

        mcp_url = f"http://127.0.0.1:{env['PHASE4_MCP_PORT']}"
        idp_url = f"http://127.0.0.1:{env['PHASE4_IDP_PORT']}"
        prometheus_url = f"http://127.0.0.1:{env['PHASE4_PROMETHEUS_PORT']}"
        otel_health_url = f"http://127.0.0.1:{env['PHASE4_OTEL_HEALTH_PORT']}"

        _wait_for(
            "OTLP collector health",
            lambda: _json_request(otel_health_url)[0] == 200,
            deadline=deadline,
        )
        discovery_status, discovery = _json_request(f"{idp_url}/.well-known/openid-configuration")
        jwks_status, jwks = _json_request(f"{idp_url}/jwks")
        if discovery_status != 200 or discovery.get("issuer") != "http://reference-idp:8080":
            raise HarnessError("Reference discovery document is invalid")
        if jwks_status != 200 or len(jwks.get("keys", [])) != 1:
            raise HarnessError("Reference JWKS document is invalid")
        if "d" in jwks["keys"][0]:
            raise HarnessError("Reference JWKS exposed private key material")

        token_status, token_document = _json_request(f"{idp_url}/token")
        token = token_document.get("access_token")
        if token_status != 200 or not isinstance(token, str) or not token:
            raise HarnessError("Reference IdP did not mint an access token")

        unauthorized_status, _ = _json_request(
            f"{mcp_url}/mcp",
            method="POST",
            body={"jsonrpc": "2.0", "id": 0, "method": "tools/list", "params": {}},
        )
        if unauthorized_status != 401:
            raise HarnessError(f"Unauthenticated MCP request returned {unauthorized_status}")

        initialized_status, initialized = _strict_mcp_post(
            mcp_url,
            token,
            method="initialize",
            params={
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "phase4-harness", "version": "1.0"},
            },
            request_id=1,
        )
        if (
            initialized_status != 200
            or initialized.get("result", {}).get("protocolVersion") != PROTOCOL_VERSION
        ):
            raise HarnessError(f"Authenticated MCP initialize failed: {initialized}")

        call_status, called = _strict_mcp_post(
            mcp_url,
            token,
            method="tools/call",
            params={"name": "list-databases", "arguments": {}},
            request_id=2,
            name="list-databases",
        )
        if (
            call_status != 200
            or "error" in called
            or called.get("result", {}).get("isError") is not False
        ):
            raise HarnessError(f"Authenticated MCP tool call failed: {called}")

        _, stats = _json_request(f"{idp_url}/stats")
        if stats.get("discovery", 0) < 1 or stats.get("jwks", 0) < 1:
            raise HarnessError(f"MCP did not perform discovery/JWKS retrieval: {stats}")

        _wait_for(
            "Prometheus MCP target",
            lambda: _prometheus_value(prometheus_url, 'up{job="arangodb-mcp"}') >= 1,
            deadline=deadline,
        )
        _wait_for(
            "Prometheus tool metric",
            lambda: _prometheus_value(
                prometheus_url,
                'mcp_tool_calls_total{tool="list-databases",outcome="success"}',
            )
            >= 1,
            deadline=deadline,
        )

        def spans_exported() -> bool:
            logs = _run(
                [*compose, "logs", "--no-color", "otel-collector"],
                env=env,
                timeout=15,
                capture=True,
            ).stdout
            return all(
                span_name in logs
                for span_name in ("mcp.request", "mcp.tool.call", "arango.database")
            )

        _wait_for("OTLP span export", spans_exported, deadline=deadline)
        print(
            "Phase 4 integration passed: OIDC discovery/JWKS + signed JWT, "
            "Prometheus scrape, and OTLP spans verified."
        )
    except (HarnessError, OSError, subprocess.SubprocessError) as exc:
        failed = True
        print(f"Phase 4 integration failed: {exc}", file=sys.stderr)
        try:
            logs = _run(
                [*compose, "logs", "--no-color"],
                env=env,
                timeout=30,
                capture=True,
            )
            print(logs.stdout, file=sys.stderr)
            print(logs.stderr, file=sys.stderr)
        except (OSError, subprocess.SubprocessError):
            pass
        raise
    finally:
        if not args.keep:
            try:
                _run(
                    [*compose, "down", "--volumes", "--remove-orphans", "--timeout", "10"],
                    env=env,
                    timeout=60,
                    capture=not failed,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                if not failed:
                    raise HarnessError(f"Phase 4 cleanup failed: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-file", default=str(DEFAULT_COMPOSE))
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--keep", action="store_true", help="Keep containers for debugging")
    args = parser.parse_args()
    try:
        run_harness(args)
    except (HarnessError, OSError, subprocess.SubprocessError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
