from typing import Any, Dict, List, Optional

from pydantic import Field

from agents.aql_execution_agent import AQLExecutionAgent
from server import mcp_app

aql_agent = AQLExecutionAgent()


@mcp_app.tool(
    name="execute-aql-query",
    description="""
    ** CRITICAL PREREQUISITE: You MUST use the 'get-aql-manual' tool FIRST before using this tool! **
    
    **Executes an AQL (ArangoDB Query Language) query.** This tool *directly executes*
    a pre-formulated AQL query. The LLM is responsible for:
    - **FIRST**: Consulting the AQL manual via 'get-aql-manual' tool to understand syntax
    - **SECOND**: Consulting the optimization manual to understand performance patterns
    - **THEN**: Generating the AQL query using proper AQL syntax and optimization patterns
    - **FINALLY**: Ensuring the AQL query is syntactically correct and optimized before execution
    
    **MANDATORY WORKFLOW:**
    1. **MANDATORY**: Call 'get-aql-manual' with manual_name="aql_ref" to get AQL syntax guide
    2. **MANDATORY**: Call 'get-aql-manual' with manual_name="optimization" for performance guidance
    3. **OPTIONAL**: If translating from Cypher, also call with manual_name="cypher2aql"
    4. **ONLY THEN**: Use this tool to execute your properly formed AQL query
    
    This tool *does not* provide any assistance with writing or debugging AQL queries.
    It only executes the query that you provide in the 'aql_query' parameter.
    
    **WARNING: Attempting to write AQL queries without consulting both manuals first 
    will likely result in syntax errors, poor performance, and failed executions! **
    """,
)
async def execute_aql(
    aql_query: str = Field(
        description="""The AQL query to execute.  Provide the complete,
        correctly-formed AQL query string.  Examples include:
        - "FOR doc IN users FILTER doc.age > 25 RETURN doc"
        - "FOR v, e, p IN 1..2 OUTBOUND 'users/123' GRAPH 'mygraph' RETURN p"
        """,
    ),
    bind_vars: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""Bind variables for parameterized queries (optional).
        
        Example: {'name': 'John', 'minAge': 25}
        """,
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="""Target database name. Uses default if not specified.
        """,
    ),
) -> Dict[str, Any]:
    """Executes an AQL query against ArangoDB.

    Returns:
        Dictionary containing:
        - 'results': List of documents/objects returned by the query
        - 'count': Number of results in current batch (for pagination)
        - 'full_count': Total number of matching documents (if applicable)
        - 'extra_stats': Query execution statistics (time, scanned docs, etc.)
        - 'error': Error message if query failed

    Use the statistics to optimize query performance and understand execution.
    """
    tool_input = {
        "aql_query": aql_query,
        "bind_vars": bind_vars or {},  # Ensure it's a dict, not None
        "database_name": database_name,
    }
    result = await aql_agent.arun(tool_input)
    return result
