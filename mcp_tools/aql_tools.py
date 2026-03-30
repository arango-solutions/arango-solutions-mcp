from typing import Any, Dict, Optional

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
    will likely result in syntax errors, poor performance, and failed executions!**
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
        "operation": "execute",
        "aql_query": aql_query,
        "bind_vars": bind_vars or {},
        "database_name": database_name,
    }
    result = await aql_agent.arun(tool_input)
    return result


@mcp_app.tool(
    name="explain-aql-query",
    description="""Explains an AQL query's execution plan WITHOUT executing it.

    Returns the query optimizer's plan showing:
    - Execution nodes (EnumerateCollection, Index, Filter, Sort, etc.)
    - Which indexes will be used (or missed)
    - Estimated costs and item counts
    - Applied optimizer rules
    - Collection access patterns

    Use this to:
    - Check if a query uses indexes efficiently BEFORE running it
    - Identify full collection scans that need index optimization
    - Compare execution plans for alternative query formulations
    - Validate that optimizer rules are being applied
    - Debug slow queries without executing them

    This is a read-only, safe operation — no data is modified or read.
    """,
)
async def explain_aql_query(
    aql_query: str = Field(description="The AQL query to analyze (not executed)."),
    bind_vars: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Bind variables (needed if query uses @params).",
    ),
    all_plans: bool = Field(
        default=False,
        description="Return all possible execution plans, not just the optimal one.",
    ),
    max_plans: Optional[int] = Field(
        default=None,
        description="Maximum number of plans to generate (only with all_plans=true).",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await aql_agent.arun(
        {
            "operation": "explain",
            "aql_query": aql_query,
            "bind_vars": bind_vars or {},
            "database_name": database_name,
            "all_plans": all_plans,
            "max_plans": max_plans,
        }
    )


@mcp_app.tool(
    name="validate-aql-query",
    description="""Validates AQL query syntax without executing or planning it.

    A fast syntax check that returns whether the query is parseable.
    Use this to quickly catch syntax errors before explain or execute.

    Returns bind variable names and collection references found in the query.
    """,
)
async def validate_aql_query(
    aql_query: str = Field(description="The AQL query to validate."),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await aql_agent.arun(
        {
            "operation": "validate",
            "aql_query": aql_query,
            "database_name": database_name,
        }
    )
