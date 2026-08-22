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
from importlib.metadata import PackageNotFoundError, version

from arangodb_mcp.config import settings
from arangodb_mcp.observability.context import get_request_id, get_trace_id


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
        request_id = get_request_id()
        trace_id = get_trace_id()
        if request_id is not None:
            payload["request_id"] = request_id
        if trace_id is not None:
            payload["trace_id"] = trace_id
        audit_event = getattr(record, "audit_event", None)
        if isinstance(audit_event, dict):
            payload.update(audit_event)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class CorrelationFilter(logging.Filter):
    """Attach safe defaults so text logs also carry request and trace IDs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.trace_id = get_trace_id() or "-"
        return True


def _configure_logging() -> None:
    """Install the root log handler matching ``LOG_FORMAT`` / ``LOG_LEVEL``.

    Called before importing ``server`` so early bootstrap messages render in
    the configured format.
    """
    level = getattr(logging, settings.server.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(CorrelationFilter())
    if settings.server.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-8s [request=%(request_id)s trace=%(trace_id)s] "
                "%(message)s",
                datefmt="%m/%d/%y %H:%M:%S",
            )
        )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


_configure_logging()

from arangodb_mcp.observability.telemetry import configure_telemetry  # noqa: E402

configure_telemetry(settings.observability)

logger = logging.getLogger(__name__)

from arangodb_mcp.arango_connector import arango_connector  # noqa: E402
from arangodb_mcp.asgi.health import health_app  # noqa: E402, F401 — compatibility import
from arangodb_mcp.server import mcp_app  # noqa: E402

# Hosts treated as loopback for the auth-token startup guard.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


async def _serve_http_with_database(server) -> None:
    """Own the database lifecycle for the standalone HTTP server.

    The official MCP SDK's ASGI app factory owns transport state but does not
    invoke this service's database lifespan. This boundary keeps readiness
    false until the connector is initialized and guarantees clean shutdown.
    """
    try:
        await asyncio.wait_for(
            arango_connector.connect(),
            timeout=settings.server.startup_connect_budget,
        )
        logger.info("ArangoDB connection established successfully")
    except Exception as e:
        # See arango_db_lifespan: readiness must not gate the transport.
        logger.error(
            "Serving WITHOUT a verified ArangoDB connection (%s: %s). Hosts: %s.",
            type(e).__name__,
            e or "timed out",
            settings.arango.hosts,
        )
    try:
        await server.serve()
    finally:
        await arango_connector.disconnect()
        logger.info("ArangoDB connection closed")


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
    """Build the composed ASGI app and serve it via uvicorn.

    Falls back to ``mcp_app.run(...)`` only if the FastMCP version does not
    expose ASGI app factories. In that case, if a token was configured we exit
    non-zero rather than silently disabling auth.
    """
    has_factories = hasattr(mcp_app, "streamable_http_app") and hasattr(mcp_app, "sse_app")

    oidc_enabled = bool(settings.identity.mcp_oidc_issuer)
    if not has_factories:
        if plain_token or oidc_enabled:
            logger.error(
                "HTTP authentication is configured but this MCP SDK version does not expose "
                "an ASGI app factory; auth cannot be enforced. Refusing to start."
            )
            sys.exit(3)
        logger.warning(
            "The MCP SDK does not expose an ASGI app factory on this version; running via "
            "mcp_app.run() without middleware. Loopback bind only.",
        )
        mcp_app.run(transport=transport)
        return

    from arangodb_mcp.asgi.app_factory import create_http_app

    app = create_http_app(transport, plain_token)

    import uvicorn

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=settings.server.log_level.lower(),
    )
    server = uvicorn.Server(config)
    asyncio.run(_serve_http_with_database(server))


def run_server_cli(argv: list[str] | None = None):
    """CLI entry point for the server."""
    arguments = sys.argv[1:] if argv is None else argv
    if "--version" in arguments:
        try:
            package_version = version("arangodb-mcp-server")
        except PackageNotFoundError:
            package_version = settings.server.server_version
        print(f"arangodb-mcp {package_version}")
        return

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
            oidc_enabled = bool(settings.identity.mcp_oidc_issuer)
            is_loopback = host in _LOOPBACK_HOSTS

            if plain_token and oidc_enabled:
                logger.error(
                    "MCP_AUTH_TOKEN and MCP_OIDC_ISSUER cannot both be configured. "
                    "Choose exactly one HTTP authentication mode."
                )
                sys.exit(2)

            if oidc_enabled:
                from arangodb_mcp.asgi.app_factory import validate_oidc_settings

                # Parse every required field and trusted credential mapping before
                # opening a network listener. Discovery remains refreshable at request time.
                validate_oidc_settings()
            elif not plain_token:
                if not is_loopback:
                    logger.error(
                        "Neither MCP_AUTH_TOKEN nor MCP_OIDC_ISSUER is set and MCP_HOST=%r "
                        "is non-loopback. "
                        "Refusing to start an unauthenticated HTTP transport on a public "
                        "interface. Configure authentication, or bind to 127.0.0.1.",
                        host,
                    )
                    sys.exit(2)
                logger.warning(
                    "HTTP authentication is not configured; loopback transport on %r has NO auth.",
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
