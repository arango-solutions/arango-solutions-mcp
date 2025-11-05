from typing import Any, Dict, List, Optional

from pydantic import Field

from agents.aql_execution_agent import AQLExecutionAgent
from server import mcp_app

aql_agent = AQLExecutionAgent()


@mcp_app.tool(
    name="execute-aql-query",
    description="""
    **INTELLIGENT AQL QUERY PROCESSOR AND EXECUTOR**
    
    **CRITICAL: This tool expects you to follow the proper workflow BEFORE calling it!**
    
    **FOR NATURAL LANGUAGE REQUESTS:**
    - First EXPLORE database structure using tools (list-collections, read-documents-with-filter, etc.)
    - Then call 'get-aql-manual' with manual_name="aql_ref" and "optimization"
    - Then create informed AQL based on actual database structure and manual guidelines
    - Finally call this tool with the optimized AQL
    
    **FOR AQL QUERY OPTIMIZATION:**
    - First UNDERSTAND the given AQL query to analyze what it's trying to achieve
    - Then EXPLORE database structure being queried using database tools
    - Then call 'get-aql-manual' with manual_name="aql_ref" and "optimization"
    - Then analyze and improve the query based on manual guidelines
    - Finally call this tool with the optimized version
    
    **FOR CYPHER CONVERSION:**
    **DETECTION: Cypher uses MATCH, WHERE, RETURN keywords (NOT FOR, FILTER, WITH)**
    - First call 'get-aql-manual' with manual_name="cypher2aql" to understand Cypher syntax
    - Then ANALYZE the Cypher query to understand variables, patterns, and intent
    - Then EXPLORE database structure using database tools
    - Then call 'get-aql-manual' with manual_name="aql_ref" and "optimization"
    - Then convert Cypher to ACTUAL AQL syntax (FOR/FILTER/RETURN not MATCH/WHERE/RETURN)
    - **CRITICAL**: Cypher and AQL are completely different - DO NOT copy Cypher and call it AQL!
    - **MANDATORY**: Finally call this tool with the converted AQL - DO NOT just show the AQL, EXECUTE IT!
    
    **INTELLIGENT AUTO-DETECTION:**
    - Silently analyze input patterns and follow the appropriate workflow
    - Don't announce what you think the input type is - just proceed correctly
    - Use syntax patterns to determine workflow, not explicit identification
    
    **CRITICAL PRINCIPLES:**
    - ALWAYS explore database structure using available tools before writing queries
    - NEVER generate AQL from thin air - base it on actual database exploration
    - Silently detect input type and follow appropriate workflow automatically
    
    This tool executes the final AQL query after proper preparation and optimization.
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
        "bind_vars": bind_vars or {},
        "database_name": database_name,
    }
    result = await aql_agent.arun(tool_input)
    return result
