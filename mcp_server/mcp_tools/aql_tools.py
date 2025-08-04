from typing import Any, Dict, List, Optional

from pydantic import Field

from ..agents.aql_execution_agent import AQLExecutionAgent
from ..server import mcp_app

aql_agent = AQLExecutionAgent()


@mcp_app.tool(
    name="execute-aql-query",  # MCP tool names often use hyphens
    description="Executes an ArangoDB Query Language (AQL) query against a specified or default database.",
)
async def execute_aql(
    aql_query: str = Field(description="The AQL query string to execute."),
    bind_vars: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Bind variables for the AQL query. Example: {'name': 'John Doe'}",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional: The name of the database to query. Defaults to the server's preconfigured default database if not provided.",
    ),
) -> Dict[str, Any]:
    """
    Executes an AQL query.
    Returns a dictionary with 'results', 'count', 'full_count', and 'extra_stats', or an 'error' field.
    """
    tool_input = {
        "aql_query": aql_query,
        "bind_vars": bind_vars or {},  # Ensure it's a dict, not None
        "database_name": database_name,
    }
    result = await aql_agent.arun(tool_input)
    return result
