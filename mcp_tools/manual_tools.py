from typing import Any, Dict, Optional

from pydantic import Field

from agents.manual_management_agent import ManualManagementAgent
from server import mcp_app

manual_agent = ManualManagementAgent()


@mcp_app.tool(
    name="get-aql-manual",
    description="""
    **🚨 CRITICAL: This tool MUST be used FIRST for ALL ArangoDB queries and operations! 🚨**
    
    **MANDATORY WORKFLOW:**
    - **ALWAYS** start with this tool before ANY AQL query generation or execution
    - **REQUIRED** before using 'execute-aql-query' tool
    - **ESSENTIAL** for understanding proper AQL syntax and functions
    
    **Why this tool is required first:**
    - Provides the complete AQL reference manual with syntax rules
    - Contains function definitions and usage examples  
    - Includes Cypher-to-AQL translation patterns
    - Ensures queries are properly formatted and functional
    
    **Available manuals:**
    - **aql_ref**: Complete AQL reference manual. Use this for:
        - Understanding AQL syntax, structure, and grammar
        - Finding information about built-in AQL functions
        - Looking up operators, data types, and keywords
        - Learning query patterns and best practices
        
    - **cyphertoaql**: Cypher-to-AQL translation guide. Use this when:
        - Translating Neo4j Cypher queries to AQL
        - Converting graph patterns with labels and relationships
        - Understanding differences between Cypher and AQL syntax
    
    **⚠️ WARNING: Attempting to write AQL queries without consulting this manual first 
    will likely result in syntax errors and failed executions! ⚠️**
    
    **PROPER WORKFLOW:**
    1. **FIRST**: Call this tool with manual_name="aql_ref"
    2. **STUDY**: Read the returned manual content carefully
    3. **THEN**: Write your AQL query based on the manual's syntax
    4. **FINALLY**: Execute the query using 'execute-aql-query'
    """,
)
async def get_aql_manuals(
    manual_name: str = Field(
        description="""The name of the manual to retrieve.

        Options:
        - aql_ref:  General AQL reference.
        - cyphertoaql: Guide to translating Cypher.
        """,
    )
) -> Dict[str, Any]:
    """Retrieves a specific AQL manual."""
    return await manual_agent.arun({"operation": "get_aql_manual", "manual_name": manual_name})
