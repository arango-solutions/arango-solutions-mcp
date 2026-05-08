"""
ArangoDB MCP Server - Main entry point

This module provides the main entry point for the ArangoDB Model Context Protocol server.
It can be used as a standalone server or imported by MCP clients like Cursor, Claude Desktop, etc.

Cross-platform compatible entry point that works on Windows, macOS, and Linux.
"""

import asyncio
import json
import logging
import platform
import sys
import time

from config import settings


class JsonFormatter(logging.Formatter):
    """One-line JSON formatter for log aggregation pipelines.

    Emits only well-known fields to avoid accidentally leaking arbitrary
    ``LogRecord.__dict__`` contents (e.g. AQL bind-vars passed via ``extra``).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    """Install the root log handler matching ``LOG_FORMAT`` / ``LOG_LEVEL``.

    Called before importing ``server`` so early bootstrap messages render in
    the configured format.
    """
    level = getattr(logging, settings.server.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    if settings.server.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-8s %(message)s",
                datefmt="%m/%d/%y %H:%M:%S",
            )
        )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


_configure_logging()

logger = logging.getLogger(__name__)

from arango_connector import arango_connector  # noqa: E402
from server import mcp_app  # noqa: E402

# Hosts treated as loopback for the auth-token startup guard.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


async def health_app(scope, receive, send):
    """Tiny ASGI app serving ``GET /healthz``.

    Returns 200 + ``{"status":"ok", "server_version": ...}`` when the
    ArangoDB connection is healthy, 503 + ``{"status":"unhealthy"}`` otherwise.
    Wrong methods get 405. Always JSON.
    """
    if scope.get("method") != "GET":
        await send(
            {
                "type": "http.response.start",
                "status": 405,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"allow", b"GET"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b'{"error":"method not allowed"}'})
        return

    healthy = await asyncio.to_thread(arango_connector.health_check)
    if healthy:
        body = json.dumps(
            {
                "status": "ok",
                "server_version": arango_connector.server_version,
            }
        ).encode()
        status = 200
    else:
        body = b'{"status":"unhealthy"}'
        status = 503

    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _health_or_app(health, app, scope, receive, send):
    """Dispatch ``/healthz`` to ``health`` and everything else to ``app``.

    Used when bearer-token auth is disabled (loopback only) so ``/healthz``
    is still reachable without going through the auth middleware.
    """
    if scope.get("type") == "http" and scope.get("path") == "/healthz":
        await health(scope, receive, send)
        return
    await app(scope, receive, send)


def setup_event_loop_policy():
    """Configure the appropriate event loop policy for the current platform."""
    system = platform.system().lower()

    if system == "windows":
        # On Windows, ProactorEventLoop is better for subprocesses and stdio
        # Set this before any async operations start
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logger.debug("Set Windows ProactorEventLoop policy")
        except AttributeError:
            # Fallback for older Python versions
            logger.debug("WindowsProactorEventLoopPolicy not available, using default")
    elif system in ["darwin", "linux"]:
        # Unix-like systems (macOS, Linux) work well with the default selector event loop
        # No special configuration needed, but we log for debugging
        logger.debug(f"Using default event loop policy for {system}")
    else:
        # Other platforms (FreeBSD, etc.) - use default
        logger.debug(f"Using default event loop policy for unknown platform: {system}")


def _run_http_transport(transport: str, host: str, port: int, plain_token: str) -> None:
    """Build the inner Starlette app, optionally wrap it with bearer-token auth,
    and serve it via uvicorn.

    Falls back to ``mcp_app.run(...)`` only if the FastMCP version does not
    expose ASGI app factories. In that case, if a token was configured we exit
    non-zero rather than silently disabling auth.
    """
    has_factories = hasattr(mcp_app, "streamable_http_app") and hasattr(mcp_app, "sse_app")

    if not has_factories:
        if plain_token:
            logger.error(
                "MCP_AUTH_TOKEN is set but this fastmcp version does not expose an ASGI "
                "app factory (streamable_http_app / sse_app); auth cannot be enforced. "
                "Refusing to start.",
            )
            sys.exit(3)
        logger.warning(
            "fastmcp does not expose an ASGI app factory on this version; running via "
            "mcp_app.run() without middleware. Loopback bind only.",
        )
        mcp_app.run(transport=transport)
        return

    if transport == "streamable-http":
        inner_app = mcp_app.streamable_http_app()
    else:
        inner_app = mcp_app.sse_app()

    if plain_token:
        from auth_middleware import BearerTokenAuthMiddleware

        app = BearerTokenAuthMiddleware(
            inner_app,
            plain_token,
            health_app=health_app,
            health_path="/healthz",
        )
        logger.info("Bearer-token auth ENABLED for %s transport.", transport)
    else:
        # No auth: still expose /healthz via a tiny dispatcher so the
        # endpoint is available on loopback deployments.
        async def app(scope, receive, send):
            await _health_or_app(health_app, inner_app, scope, receive, send)

    import uvicorn

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=settings.server.log_level.lower(),
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


def run_server_cli():
    """CLI entry point for the server."""
    logger.info(f"Starting {settings.server.server_name} v{settings.server.server_version}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Default database: {settings.arango.default_db_name}")

    try:
        setup_event_loop_policy()

        transport = settings.server.mcp_transport.lower()
        if transport in ("sse", "streamable-http"):
            host = settings.server.mcp_host
            port = settings.server.mcp_port
            token = settings.server.mcp_auth_token
            plain_token = token.get_secret_value() if token is not None else ""
            is_loopback = host in _LOOPBACK_HOSTS

            if not plain_token:
                if not is_loopback:
                    logger.error(
                        "MCP_AUTH_TOKEN is not set and MCP_HOST=%r is non-loopback. "
                        "Refusing to start an unauthenticated HTTP transport on a public "
                        "interface. Set MCP_AUTH_TOKEN, or bind to 127.0.0.1.",
                        host,
                    )
                    sys.exit(2)
                logger.warning(
                    "MCP_AUTH_TOKEN is not set; HTTP transport on loopback %r has NO auth.",
                    host,
                )

            logger.info(f"Starting MCP server with {transport} transport on {host}:{port}")
            _run_http_transport(transport, host, port, plain_token)
        else:
            logger.info("Starting MCP server with stdio transport...")
            mcp_app.run(transport="stdio")

    except KeyboardInterrupt:
        # The lifespan manager in FastMCP will handle graceful shutdown of the
        # ArangoDB connection when KeyboardInterrupt is caught here.
        logger.info("Server shutdown requested by user. Exiting.")
        sys.exit(0)
    except SystemExit:
        # Re-raise sys.exit() calls (e.g. from the auth-token startup guard)
        # without wrapping them in the generic failure path below.
        raise
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server_cli()
