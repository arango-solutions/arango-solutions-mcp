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
    """CLI entry point for the server.
    
    Supports both STDIO and HTTP transports based on configuration.
    
    Environment Variables:
        MCP_TRANSPORT: 'stdio' (default) or 'http'
        MCP_HTTP_HOST: HTTP bind address (default: 0.0.0.0)
        MCP_HTTP_PORT: HTTP port (default: 8000)
    """
    logger.info(f"Starting {settings.server.server_name} v{settings.server.server_version}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Default database: {settings.arango.default_db_name}")

    try:
        setup_event_loop_policy()

        transport = settings.server.transport.lower()
        
        if transport == "http":
            logger.info("=" * 70)
            logger.info("Starting MCP server with HTTP Streamable transport...")
            logger.info(f"HTTP Server: http://{settings.server.http_host}:{settings.server.http_port}")
            logger.info(f"MCP Endpoint: http://{settings.server.http_host}:{settings.server.http_port}/mcp")
            logger.info("=" * 70)
            logger.info("HTTP transport enables:")
            logger.info("  - Multiple concurrent clients")
            logger.info("  - Network accessibility")
            logger.info("  - Integration with Cline, OpenCode, and web clients")
            logger.info("=" * 70)
            
            # Use Uvicorn to run the HTTP server with ASGI app
            import uvicorn
            from server import app
            
            logger.info("Starting with Uvicorn ASGI server (production mode)...")
            uvicorn.run(
                app,
                host=settings.server.http_host,
                port=settings.server.http_port,
                log_level=settings.server.log_level.lower()
            )
        else:
            logger.info("Starting MCP server with STDIO transport...")
            logger.info("STDIO transport is ideal for:")
            logger.info("  - Cursor IDE integration")
            logger.info("  - Claude Desktop integration")
            logger.info("  - Local development and testing")
            
            mcp_app.run(transport="stdio")

    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server_cli()
