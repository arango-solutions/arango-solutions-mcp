from typing import Any, Dict, List, Optional

from pydantic import Field

from agents.aql_execution_agent import AQLExecutionAgent
from server import mcp_app

aql_agent = AQLExecutionAgent()


@mcp_app.tool(
    name="execute-aql-query",
    description="""Executes an ArangoDB Query Language (AQL) query for complex data operations and retrieval.
    
    AQL is ArangoDB's powerful query language that supports:
    - Document queries with filtering, sorting, and aggregation
    - Graph traversals and pattern matching  
    - Joins across collections
    - Mathematical and string operations
    - Full-text search integration
    - Geospatial queries
    
    Use this tool for:
    - Complex data retrieval that simple CRUD can't handle
    - Graph analysis and traversals
    - Analytics and reporting queries
    - Multi-collection operations
    - Data transformation and aggregation
    
    Safety: Only read operations (FOR, RETURN, FILTER, SORT, LIMIT) are recommended.
    Write operations (INSERT, UPDATE, REMOVE, REPLACE) should be used with caution.
    """,
)
async def execute_aql(
    aql_query: str = Field(
        description="""The AQL query to execute. Should be well-formed AQL syntax.
        
        Examples:
        - Simple query: "FOR doc IN users FILTER doc.age > 25 RETURN doc"
        - With sorting: "FOR doc IN products FILTER doc.category == 'electronics' SORT doc.price DESC RETURN doc"
        - Graph traversal: "FOR v, e, p IN 1..3 OUTBOUND 'users/john' GRAPH 'social' RETURN p"
        - Aggregation: "FOR doc IN orders COLLECT category = doc.category AGGREGATE total = SUM(doc.amount) RETURN {category, total}"
        - Join collections: "FOR user IN users FOR order IN orders FILTER user._key == order.user_key RETURN {user: user.name, order: order.total}"
        
        Always validate your AQL syntax. Use EXPLAIN to understand query performance.
        """
    ),
    bind_vars: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""Bind variables for parameterized queries (recommended for security).
        
        Use @variable_name in your AQL query and provide values here.
        
        Examples:
        - {'name': 'John', 'minAge': 25} for query "FOR doc IN users FILTER doc.name == @name AND doc.age > @minAge RETURN doc"
        - {'categories': ['electronics', 'books']} for query "FOR doc IN products FILTER doc.category IN @categories RETURN doc"
        - {'startDate': '2023-01-01', 'endDate': '2023-12-31'} for date range queries
        
        Using bind variables prevents AQL injection and improves query caching.
        """,
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="""Target database name. If not specified, uses the server's default database.
        
        Examples:
        - 'production' - for production data
        - 'analytics' - for analytics database
        - 'test' - for testing environment
        
        Leave empty to use the default database configured in server settings.
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
