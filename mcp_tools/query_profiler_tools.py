from typing import Any, Dict, List, Optional

from pydantic import Field

from agents.query_profiler_agent import QueryProfilerAgent
from server import mcp_app

profiler_agent = QueryProfilerAgent()


@mcp_app.tool(
    name="profile-aql-query",
    description="""
    🚨 CRITICAL: MANDATORY TOOL FOR ALL QUERY OPTIMIZATION REQUESTS 🚨
    
    ⛔ DO NOT CREATE "OPTIMIZED" QUERIES WITHOUT CALLING THIS TOOL FIRST ⛔
    
    ⚠️ OPTIMIZATION WORKFLOW - STEP 2 (MANDATORY):
    Before calling this tool, VERIFY:
    ✓ Step 1 Complete: Called get-aql-manual("aql_ref") AND get-aql-manual("optimization")
    ✗ If Step 1 incomplete → STOP! Complete Step 1 first!
    
    After calling this tool, you MUST COMPLETE:
    → Step 3: Explore database (list-collections, get-collection-properties, list-indexes)
    → Step 4: Create optimized query based on profiling data
    → Step 5: Call compare-aql-queries or explain-aql-query to VERIFY optimization
    
    ⚠️ SKIPPING STEP 2, 3, OR 5 WILL RESULT IN INVALID OPTIMIZATIONS ⚠️
    
    ═══════════════════════════════════════════════════════════
    
    Execute an AQL query with comprehensive performance profiling enabled.
    
    This tool provides detailed performance metrics including:
    - Execution time breakdown by query stage (parsing, optimizing, executing)
    - Node-by-node execution statistics (calls, items, filtered, runtime)
    - Memory usage and peak memory consumption
    - Indexes used and their selectivity
    - Optimization rules applied by the query optimizer
    - Document scan statistics (full scans vs index scans)
    
    **Profile Levels:**
    - 1: Basic profiling with timing breakdown
    - 2: Full profiling with execution plan and node-level statistics (recommended)
    
    **Use this tool to:**
    - Analyze query performance and identify bottlenecks
    - Verify which indexes are actually being used
    - Understand how the optimizer executes your query
    - Compare execution metrics before and after optimization
    - Make data-driven optimization decisions
    
    **Example Use Case:**
    Before suggesting query optimizations, profile both the original and 
    "optimized" queries to verify which one actually performs better with
    your real data.
    """,
)
async def profile_aql_query(
    aql_query: str = Field(
        description="AQL query to profile and execute.",
    ),
    bind_vars: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Bind variables for parameterized queries.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database name. Uses default if not specified.",
    ),
    profile_level: int = Field(
        default=2,
        description="Profiling detail level: 1 (basic) or 2 (full with execution plan).",
    ),
) -> Dict[str, Any]:
    """
    Execute and profile an AQL query with detailed performance metrics.
    
    Returns comprehensive profiling data including:
    - Query results
    - Execution time and memory usage
    - Statistics (documents scanned, filtered, etc.)
    - Profile data (timing per query stage)
    - Execution plan (with profile_level=2)
    - Indexes used
    - Optimization rules applied
    """
    tool_input = {
        "operation": "profile_query",
        "aql_query": aql_query,
        "bind_vars": bind_vars or {},
        "database_name": database_name,
        "profile_level": profile_level,
    }
    return await profiler_agent.arun(tool_input)


@mcp_app.tool(
    name="compare-aql-queries",
    description="""
    🚨 CRITICAL: MANDATORY VERIFICATION TOOL FOR ALL OPTIMIZATIONS 🚨
    
    ⛔ NEVER PROVIDE "OPTIMIZED" QUERY WITHOUT CALLING THIS TOOL ⛔
    
    ⚠️ OPTIMIZATION WORKFLOW - STEP 5 (MANDATORY):
    Before calling this tool, VERIFY ALL PREVIOUS STEPS:
    ✓ Step 1: Called get-aql-manual("aql_ref") AND get-aql-manual("optimization")
    ✓ Step 2: Called profile-aql-query on ORIGINAL user query
    ✓ Step 3: Called list-collections, get-collection-properties, list-indexes
    ✓ Step 4: Created optimized query based on profiling data
    ✗ If ANY step incomplete → STOP! Complete all steps first!
    
    This tool PROVES whether your optimization actually works!
    Without this verification, you may make performance WORSE.
    
    ═══════════════════════════════════════════════════════════
    
    Execute and compare multiple AQL queries to determine which performs best.
    
    This tool profiles each query and provides side-by-side comparison of:
    - Execution time
    - Memory usage
    - Number of results
    - Indexes used
    - Documents scanned (full scan vs index scan)
    - Optimization rules applied
    
    **Use this tool to:**
    - Compare original vs optimized query performance
    - Test different query approaches (vertex-first vs edge-first)
    - Validate optimization decisions with real data
    - A/B test query variations
    - Identify the fastest query among multiple alternatives
    
    **Perfect for avoiding optimization mistakes:**
    Instead of blindly applying optimization patterns, use this tool to
    test and compare actual performance with your data before committing
    to a specific approach.
    
    **Example:**
    Compare a vertex-first query against an edge-first query to see which
    is faster for your specific data distribution and filter selectivity.
    """,
)
async def compare_aql_queries(
    queries: List[Dict[str, Any]] = Field(
        description="""
        List of queries to compare. Each query should be a dictionary with:
        - 'name': A descriptive name for the query (e.g., "Original Query", "Optimized Query")
        - 'query': The AQL query string
        - 'bind_vars': Optional dictionary of bind variables
        
        Example:
        [
            {
                "name": "Vertex-First Approach",
                "query": "FOR v IN vertices FILTER v.name == @name FOR e IN edges FILTER e._from == v._id RETURN e",
                "bind_vars": {"name": "test"}
            },
            {
                "name": "Edge-First Approach", 
                "query": "FOR e IN edges FOR v IN vertices FILTER v._id == e._from AND v.name == @name RETURN e",
                "bind_vars": {"name": "test"}
            }
        ]
        """,
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database name. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    """
    Execute and compare multiple queries to find the best performing one.
    
    Returns:
    - Comparison results for all queries
    - Best query recommendation
    - Performance summary and speedup metrics
    - Full profiling data for each query
    """
    tool_input = {
        "operation": "compare_queries",
        "queries": queries,
        "database_name": database_name,
    }
    return await profiler_agent.arun(tool_input)


@mcp_app.tool(
    name="explain-aql-query",
    description="""
    🚨 ALTERNATIVE VERIFICATION TOOL (Use if compare-aql-queries unavailable) 🚨
    
    ⛔ NEVER PROVIDE "OPTIMIZED" QUERY WITHOUT VERIFICATION ⛔
    
    ⚠️ OPTIMIZATION WORKFLOW - STEP 5a (ALTERNATIVE VERIFICATION):
    Before calling this tool, VERIFY ALL PREVIOUS STEPS:
    ✓ Step 1: Called get-aql-manual("aql_ref") AND get-aql-manual("optimization")
    ✓ Step 2: Called profile-aql-query on ORIGINAL user query
    ✓ Step 3: Called list-collections, get-collection-properties, list-indexes
    ✓ Step 4: Created optimized query based on profiling data
    ✗ If ANY step incomplete → STOP! Complete all steps first!
    
    Note: Prefer compare-aql-queries for real performance data.
    Use explain-aql-query only for estimated costs without execution.
    
    ═══════════════════════════════════════════════════════════
    
    Get the execution plan for an AQL query WITHOUT executing it.
    
    This tool shows how ArangoDB would execute the query, including:
    - Execution plan nodes and their order
    - Estimated cost and number of items
    - Which indexes would be used
    - Optimization rules that would be applied
    - Filter conditions and their placement
    
    **Use this tool to:**
    - Preview query execution without running expensive queries
    - Verify index usage before execution
    - Understand the optimizer's strategy
    - Compare execution plans of different query variations
    - Debug why a query isn't using expected indexes
    
    **Advantages over execution:**
    - Fast (no actual data processing)
    - Safe (doesn't modify data or hold locks)
    - Can analyze queries on large datasets without waiting
    - Get all optimization plans (with all_plans=True)
    
    **Use Case:**
    Before executing a potentially slow query, use EXPLAIN to verify it
    will use appropriate indexes and has reasonable estimated cost.
    """,
)
async def explain_aql_query(
    aql_query: str = Field(
        description="AQL query to explain (not execute).",
    ),
    bind_vars: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Bind variables for parameterized queries.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database name. Uses default if not specified.",
    ),
    all_plans: bool = Field(
        default=False,
        description="If True, return all possible execution plans. If False, return only the optimal plan.",
    ),
) -> Dict[str, Any]:
    """
    Explain query execution plan without running the query.
    
    Returns:
    - Execution plan (or multiple plans if all_plans=True)
    - Estimated cost and result count
    - Indexes that would be used
    - Optimization rules that would be applied
    """
    tool_input = {
        "operation": "explain_query",
        "aql_query": aql_query,
        "bind_vars": bind_vars or {},
        "database_name": database_name,
        "all_plans": all_plans,
    }
    return await profiler_agent.arun(tool_input)

