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
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logger.debug("Set Windows ProactorEventLoop policy")
        except AttributeError:
            logger.debug("WindowsProactorEventLoopPolicy not available, using default")
    elif system in ["darwin", "linux"]:
        logger.debug(f"Using default event loop policy for {system}")
    else:
        logger.debug(f"Using default event loop policy for unknown platform: {system}")


def run_server_cli():
    """CLI entry point for the server."""
    logger.info(f"Starting {settings.server.server_name} v{settings.server.server_version}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Default database: {settings.arango.default_db_name}")

    try:
        setup_event_loop_policy()

        logger.info("Starting MCP server with stdio transport...")
        mcp_app.run(transport="stdio")

    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server_cli()
