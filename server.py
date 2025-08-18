from mcp.server.fastmcp import FastMCP

from arango_connector import arango_db_lifespan
from config import settings

# Explicitly define the server name and instructions
_server_name = "ArangoDB_MCP_Server"
_server_instructions = f"""
Interact with ArangoDB multi-model database for document, graph, and search operations.

**CRITICAL WORKFLOW REQUIREMENT** 
**ALWAYS use 'get-aql-manual' tool FIRST before ANY AQL query operations!**
This tool provides essential AQL syntax, functions, and examples needed for correct query formation.

**MANDATORY SEQUENCE for AQL queries:**
1. **FIRST**: Call 'get-aql-manual' with manual_name="aql_ref" 
2. **STUDY**: Review the AQL syntax and functions from the manual
3. **THEN**: Write your AQL query using proper syntax from the manual
4. **FINALLY**: Execute using 'execute-aql-query' tool

This server provides comprehensive access to ArangoDB functionality including:
- AQL query execution for complex data retrieval (REQUIRES manual consultation first!)
- Document CRUD operations with collections
- Graph management with vertices and edges  
- Full-text search and analyzers
- Database and collection management
- Index management for performance optimization
- View management for search and aggregation

Default database: '{settings.arango.default_db_name}'

All operations support optional database selection. When no database is specified, 
the default database will be used. The server maintains persistent connections 
and handles authentication automatically.

For best results:
- **ALWAYS consult AQL manual before writing queries**
- Specify collection names clearly
- Use descriptive field names in document operations
- Leverage AQL for complex queries and data relationships
- Consider indexing for frequently queried fields
"""

# Create the FastMCP application instance
mcp_app = FastMCP(name=_server_name, instructions=_server_instructions, lifespan=arango_db_lifespan)

# Import tool and resource modules to register them
# These imports MUST happen AFTER mcp_app is defined.
from mcp_tools import (
    analyzer_tools,
    aql_tools,
    collection_tools,
    database_tools,
    document_tools,
    graph_tools,
    index_tools,
    manual_tools,
    view_tools,
)
