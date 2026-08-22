"""Pinned internal telemetry conventions for the MCP operations contract.

Changing these names or attribute meanings requires incrementing
``CONVENTION_VERSION`` and updating the compatibility tests.
"""

CONVENTION_VERSION = "arangodb-mcp/1.0"

SPAN_MCP_REQUEST = "mcp.request"
SPAN_MCP_TOOL_CALL = "mcp.tool.call"
SPAN_ARANGO_DATABASE = "arango.database"
SPAN_DEPENDENCY_EMBEDDING = "dependency.embedding"

ATTR_CONVENTION_VERSION = "arangodb_mcp.convention.version"
ATTR_REQUEST_ID = "mcp.request.id"
ATTR_TRANSPORT = "mcp.transport"
ATTR_TOOL_NAME = "mcp.tool.name"
ATTR_TOOL_OPERATION = "mcp.tool.operation"
ATTR_TOOL_CATEGORY = "mcp.tool.category"
ATTR_OUTCOME = "mcp.outcome"
ATTR_DB_OPERATION = "db.operation.name"
ATTR_DEPENDENCY_NAME = "server.address"
