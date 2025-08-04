import anyio

from .config import settings  # For host/port if running HTTP
from .server import mcp_app  # Import the configured FastMCP instance

# import uvicorn # No longer needed if not using the detailed uvicorn setup



def run_server_cli():
    """
    Runs the MCP server using Streamable HTTP.
    """
    print(f"Starting ArangoDB MCP Server ({mcp_app.name})...")
    print(
        f"Default ArangoDB: {settings.arango.hosts}, DB: {settings.arango.default_db_name}"
    )
    print(f"GEMINI API Key loaded: {'Yes' if settings.llm.gemini_api_key else 'No'}")

    print(
        f"MCP Server will run on http://{mcp_app.settings.host}:{mcp_app.settings.port}/mcp"
    )

    # Run with Streamable HTTP
    anyio.run(mcp_app.run_streamable_http_async)


if __name__ == "__main__":
    run_server_cli()
