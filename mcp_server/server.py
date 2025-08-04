from mcp.server.fastmcp import FastMCP

from .arango_connector import arango_db_lifespan
from .config import settings

# Explicitly define the name
_server_name = "ArangoDB_MCP_Chatbot_Server"
_server_instructions = (
    f"Interact with ArangoDB (default DB: '{settings.arango.default_db_name}')."
)

# Create the FastMCP application instance
mcp_app = FastMCP(
    name=_server_name, instructions=_server_instructions, lifespan=arango_db_lifespan
)


# Import tool and resource modules to register them
# These imports MUST happen AFTER mcp_app is defined.
from .mcp_tools import (analyzer_tools, aql_tools, collection_tools,
                        database_tools, document_tools, graph_tools,
                        index_tools, view_tools)
