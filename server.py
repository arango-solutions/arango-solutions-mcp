from mcp.server.fastmcp import FastMCP

from arango_connector import arango_db_lifespan
from config import settings


# Explicitly define the server name and instructions
_server_name = "ArangoDB_MCP_Server"
_server_instructions = f"""
Interact with ArangoDB multi-model database for document, graph, and search operations.

This server provides comprehensive access to ArangoDB functionality including:
- Document CRUD operations with collections
- Graph management with vertices and edges  
- AQL query execution for complex data retrieval
- Full-text search and analyzers
- Database and collection management
- Index management for performance optimization
- View management for search and aggregation

Default database: '{settings.arango.default_db_name}'

All operations support optional database selection. When no database is specified, 
the default database will be used. The server maintains persistent connections 
and handles authentication automatically.

For best results:
- Specify collection names clearly
- Use descriptive field names in document operations
- Leverage AQL for complex queries and data relationships
- Consider indexing for frequently queried fields
"""

# Create the FastMCP application instance
mcp_app = FastMCP(
    name=_server_name,
    instructions=_server_instructions,
    lifespan=arango_db_lifespan
)

# Import tool and resource modules to register them
# These imports MUST happen AFTER mcp_app is defined.
from mcp_tools import (
    aql_tools, 
    database_tools,
    collection_tools, 
    document_tools,   
    index_tools,      
    graph_tools,      
    analyzer_tools,
    view_tools   
)