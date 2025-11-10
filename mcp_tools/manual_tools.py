from typing import Any, Dict, Optional

from pydantic import Field

from agents.manual_management_agent import ManualManagementAgent
from server import mcp_app

manual_agent = ManualManagementAgent()


@mcp_app.tool(
    name="get-aql-manual",
    description="""
    🚨 CRITICAL: THIS TOOL MUST BE CALLED FIRST FOR ALL AQL OPERATIONS! 🚨
    
    ⛔ NEVER SKIP THIS STEP - IT PREVENTS SYNTAX ERRORS AND POOR PERFORMANCE ⛔
    
    ⚠️ OPTIMIZATION WORKFLOW - STEP 1 (MANDATORY - ALWAYS FIRST):
    When user requests query optimization, you MUST:
    1. Call: get-aql-manual(manual_name="aql_ref") 
    2. Call: get-aql-manual(manual_name="optimization")
    3. Study BOTH manuals before proceeding
    
    The "optimization" manual contains the complete 6-step workflow you MUST follow!
    
    **MANDATORY WORKFLOW FOR QUERY OPTIMIZATION:**
    - STEP 1: Read these manuals (THIS TOOL) ✓
    - STEP 2: Profile original query (profile-aql-query) → MANDATORY
    - STEP 3: Explore database (list-collections, list-indexes) → MANDATORY  
    - STEP 4: Create optimized query based on data
    - STEP 5: Verify with compare-aql-queries → MANDATORY
    - STEP 6: Provide recommendations
    
    **Why Step 1 is critical:**
    - Prevents syntax errors in AQL queries
    - Provides optimization patterns and best practices
    - Contains the 6-step workflow enforcement rules
    - Explains when to use edge-first vs vertex-first patterns
    - Shows proper index usage and composite index rules
    
    **Available manuals:**
    - **aql_ref**: Complete AQL syntax reference
        - AQL grammar, keywords, operators
        - Built-in functions and data types
        - Query patterns and examples
        
    - **cypher2aql**: Cypher-to-AQL translation guide
        - Converting Neo4j Cypher to ArangoDB AQL
        - Graph pattern translation
        - Syntax differences and gotchas
        
    - **optimization**: Query optimization guide ⚠️ READ THIS FOR OPTIMIZATIONS!
        - 6-STEP OPTIMIZATION WORKFLOW (MANDATORY)
        - When to use edge-first vs vertex-first
        - Index utilization best practices
        - Vertex-centric index patterns
        - Performance testing with profile/compare tools
    
    ⚠️ WARNING: Skipping this step leads to:
    - Syntactically incorrect queries
    - "Optimizations" that make performance WORSE
    - Missing the mandatory profiling and verification steps
    - Recommending inappropriate optimization patterns
    
    **FOR QUERY OPTIMIZATION REQUESTS:**
    You MUST call this tool twice (aql_ref + optimization) before doing ANYTHING else!
    The optimization manual will tell you exactly what to do next.
    """,
)
async def get_aql_manuals(
    manual_name: str = Field(
        description="""The name of the manual to retrieve.

        Options:
        - aql_ref: General AQL reference.
        - cypher2aql: Guide to translating Cypher.
        - optimization: AQL query optimization guide.
        """,
    )
) -> Dict[str, Any]:
    """Retrieves a specific AQL manual."""
    return await manual_agent.arun({"operation": "get_aql_manual", "manual_name": manual_name})
