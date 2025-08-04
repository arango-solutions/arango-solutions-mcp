# mcp_server/mcp_tools/database_tools.py
from typing import Any, Dict, List, Optional

from pydantic import Field

from ..agents.database_management_agent import DatabaseManagementAgent
from ..server import mcp_app

db_agent = DatabaseManagementAgent()


@mcp_app.tool(
    name="list-databases",
    description="Lists all available databases in the ArangoDB instance.",
)
async def list_databases_tool_func() -> (
    Dict[str, Any]
):  # Function name can be different
    """MCP Tool to list ArangoDB databases."""
    return await db_agent.arun({"operation": "list_databases"})


@mcp_app.tool(name="create-database", description="Creates a new database in ArangoDB.")
async def create_database_tool_func(
    database_name: str = Field(description="The name of the database to create."),
) -> Dict[str, Any]:
    """MCP Tool to create an ArangoDB database."""
    return await db_agent.arun(
        {
            "operation": "create_database",
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="delete-database", description="Deletes an existing database from ArangoDB."
)
async def delete_database_tool_func(
    database_name: str = Field(description="The name of the database to delete."),
) -> Dict[str, Any]:
    """MCP Tool to delete an ArangoDB database."""
    if database_name == "_system":
        return {"error": "Deleting the _system database is not allowed via this tool."}
    return await db_agent.arun(
        {"operation": "delete_database", "database_name": database_name}
    )


@mcp_app.tool(
    name="get-database-info",
    description="Retrieves statistics and properties for a given database, or the default database if none is specified.",
)
async def get_database_info_tool_func(
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The name of the database to inspect. Defaults to the server's default database.",
    )
) -> Dict[str, Any]:
    """MCP Tool to get ArangoDB database information."""
    return await db_agent.arun(
        {"operation": "get_database_info", "database_name": database_name}
    )
