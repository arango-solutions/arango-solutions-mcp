from typing import Any, Dict, List

from pydantic import Field

from arangodb_mcp.agents.aql_execution_agent import AQLExecutionAgent
from arangodb_mcp.server import mcp_app

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
    bind_vars: Dict[str, Any] | None = Field(
        default=None,
        description="""Bind variables for parameterized queries (optional).
        
        Example: {'name': 'John', 'minAge': 25}
        """,
    ),
    database_name: str | None = Field(
        default=None,
        description="""Target database name. Uses default if not specified.
        """,
    ),
    max_runtime: float | None = Field(
        default=None,
        description="Maximum query execution time in seconds. ArangoDB will kill the query if "
        "exceeded. If unset, the server's DEFAULT_AQL_MAX_RUNTIME env var applies. Values above "
        "30 seconds are clamped, and zero cannot disable the production ceiling.",
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
        "max_runtime": max_runtime,
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
    bind_vars: Dict[str, Any] | None = Field(
        default=None,
        description="Bind variables (needed if query uses @params).",
    ),
    all_plans: bool = Field(
        default=False,
        description="Return all possible execution plans, not just the optimal one.",
    ),
    max_plans: int | None = Field(
        default=None,
        description="Maximum number of plans to generate (only with all_plans=true).",
    ),
    database_name: str | None = Field(
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
    database_name: str | None = Field(
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


@mcp_app.tool(
    name="profile-aql-query",
    description="""Executes ONE read-only AQL query with server-side profiling and returns
    its results plus MEASURED execution data: elapsed time and peak memory (from the cursor
    stats), a per-stage timing breakdown, the execution plan, the indexes the optimizer
    actually used, the optimizer rules applied, and scan statistics (full-collection vs
    index scans, documents filtered).

    Strictly read-only: the query is parsed and classified first, and any mutating or
    ambiguous query is rejected without execution — analyze those with 'explain-aql-query'.

    Use this to see how a query REALLY behaves at runtime, not just its estimated plan.
    """,
)
async def profile_aql_query(
    aql_query: str = Field(description="The read-only AQL query to execute and profile."),
    bind_vars: Dict[str, Any] | None = Field(
        default=None,
        description="Bind variables (needed if the query uses @params).",
    ),
    profile_level: int = Field(
        default=2,
        description="Profiling detail: 1 = basic stage timings and stats; "
        "2 = full plan with per-node runtime, indexes used, and optimizer rules.",
    ),
    database_name: str | None = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
    max_runtime: float | None = Field(
        default=None,
        description="Maximum execution time in seconds. Clamped to the 30-second ceiling.",
    ),
) -> Dict[str, Any]:
    return await aql_agent.arun(
        {
            "operation": "profile",
            "aql_query": aql_query,
            "bind_vars": bind_vars or {},
            "profile_level": profile_level,
            "database_name": database_name,
            "max_runtime": max_runtime,
        }
    )


@mcp_app.tool(
    name="compare-aql-queries",
    description="""Profiles TWO OR MORE read-only AQL queries and compares them. For each
    query it reports the label, measured elapsed time, result count, indexes used, and scan
    statistics.

    Crucially, it PROVES whether the queries are functionally equivalent — i.e. every query
    returns the same multiset of rows regardless of row order — before ranking speed, so a
    faster-but-different rewrite is never mistaken for a valid optimization. It reports the
    fastest query among the equivalent ones and sets a clear warning when they diverge.

    Strictly read-only: each query is classified first; a mutating/ambiguous entry is
    rejected on its own while the remaining read queries are still processed.
    """,
)
async def compare_aql_queries(
    queries: List[Dict[str, Any]] = Field(
        description="List of at least two queries to compare. Each item is an object with "
        "'label' (str), 'aql_query' (str), and optional 'bind_vars' (object).",
    ),
    database_name: str | None = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
    max_runtime: float | None = Field(
        default=None,
        description="Maximum execution time in seconds per query. Clamped to the 30-second "
        "ceiling.",
    ),
) -> Dict[str, Any]:
    return await aql_agent.arun(
        {
            "operation": "compare",
            "queries": queries,
            "database_name": database_name,
            "max_runtime": max_runtime,
        }
    )
