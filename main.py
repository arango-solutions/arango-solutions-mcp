"""
ArangoDB MCP Server - Main entry point

This module provides the main entry point for the ArangoDB Model Context Protocol server.
It can be used as a standalone server or imported by MCP clients like Cursor, Claude Desktop, etc.

Cross-platform compatible entry point that works on Windows, macOS, and Linux.
"""

import asyncio
import logging
import platform
import sys

from config import settings
from server import mcp_app

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.server.log_level.upper()),
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%m/%d/%y %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr),
    ],
)

logger = logging.getLogger(__name__)


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


def run_server_cli():
    """CLI entry point for the server."""
    logger.info(f"Starting {settings.server.server_name} v{settings.server.server_version}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Default database: {settings.arango.default_db_name}")

    try:
        # Configure event loop policy for optimal performance on each platform
        setup_event_loop_policy()

        # Run the FastMCP server. This is a synchronous, blocking call that
        # will start and manage the asyncio event loop internally.
        # It will also handle the lifespan manager to connect/disconnect from ArangoDB.
        logger.info("Starting MCP server with stdio transport...")
        mcp_app.run(transport="stdio")

    except KeyboardInterrupt:
        # The lifespan manager in FastMCP will handle graceful shutdown of the
        # ArangoDB connection when KeyboardInterrupt is caught here.
        logger.info("Server shutdown requested by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server_cli()
