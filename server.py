from mcp.server.fastmcp import FastMCP

from arango_connector import arango_db_lifespan
from config import settings

_server_name = "ArangoDB_MCP_Server"
_server_instructions = f"""
Interact with ArangoDB multi-model database for document, graph, and search operations.

**CRITICAL WORKFLOW REQUIREMENT** 
**ALWAYS use 'get-aql-manual' tool FIRST before ANY query operations!**
**ALWAYS explore database structure using available tools before writing queries!**

**WORKFLOW FOR DIFFERENT INPUT TYPES:**

**NATURAL LANGUAGE REQUESTS (e.g., "Find financial metrics connected to CINF"):**
1. **EXPLORE**: Use database tools (list-collections, read-documents-with-filter, list-graphs, etc.) to understand database structure
2. **MANUAL**: Call 'get-aql-manual' with manual_name="aql_ref" for AQL syntax
3. **OPTIMIZE**: Call 'get-aql-manual' with manual_name="optimization" for performance guidance
4. **CREATE**: Write informed AQL based on actual database structure and manual guidelines
5. **EXECUTE**: Use 'execute-aql-query' tool with the optimized AQL
6. **FINAL SUMMARY**: After execution, provide a comprehensive summary of the entire process including original input, steps taken, final query, and results

**AQL QUERY BLOCKS (e.g., user provides existing AQL for optimization):**
1. **UNDERSTAND**: Analyze the given AQL query to understand what it's trying to achieve
2. **EXPLORE**: Use database tools to understand the actual database structure being queried
3. **MANUAL**: Call 'get-aql-manual' with manual_name="aql_ref" for AQL syntax reference
4. **OPTIMIZE**: Call 'get-aql-manual' with manual_name="optimization" for performance patterns
5. **ANALYZE**: Review query against optimization guidelines and identify improvements
6. **IMPROVE**: Create optimized version with explanations of changes
7. **EXECUTE**: Use 'execute-aql-query' tool with the optimized version
8. **FINAL SUMMARY**: After execution, provide a comprehensive summary of the entire process including original input, steps taken, final query, and results

**CYPHER QUERIES (e.g., user provides Cypher for conversion):**
**DETECTION: Cypher syntax uses MATCH, WHERE, RETURN (NOT FOR, FILTER, WITH)**
1. **UNDERSTAND CYPHER**: Call 'get-aql-manual' with manual_name="cypher2aql" FIRST to understand Cypher syntax
2. **ANALYZE CYPHER**: Understand the given Cypher query:
   - What variables are used (nodes, relationships)
   - What patterns and conditions exist
   - What the query is trying to achieve
   - What terms and concepts are involved
3. **EXPLORE**: Use database tools to understand actual database structure
4. **MANUAL**: Call 'get-aql-manual' with manual_name="aql_ref" for AQL syntax
5. **OPTIMIZE**: Call 'get-aql-manual' with manual_name="optimization" for performance patterns
6. **CONVERT**: Transform Cypher to ACTUAL AQL syntax - CYPHER USES MATCH/WHERE, AQL USES FOR/FILTER - DO NOT COPY CYPHER AND CALL IT AQL!
7. **MANDATORY FINAL STEP**: MUST call 'execute-aql-query' tool with the converted AQL - DO NOT just show the AQL, EXECUTE IT!
8. **FINAL SUMMARY**: After execution, provide a well-formatted summary with clear sections:
   ```
   ## Query Conversion Summary
   
   ### Original Cypher Query:
   [Show original user input in code block]
   
   ### Converted AQL Query:
   [Show ACTUAL AQL that was executed from tool call in code block]
   
   ### Results:
   [Show execution results and key findings]
   ```
   - Use proper markdown formatting with code blocks
   - DO NOT show fake conversions - only show what was actually executed!

**CRITICAL: ACTUAL SYNTAX CONVERSION REQUIRED!**
- **CYPHER SYNTAX**: MATCH (a:Label) -[:Relation]-> (b) WHERE conditions RETURN 
- **AQL SYNTAX**: FOR a IN collection FILTER conditions FOR b IN OUTBOUND a edges RETURN
- **DO NOT COPY CYPHER AND CALL IT AQL** - they are completely different languages!
- **CONVERSION MEANS CHANGING THE SYNTAX COMPLETELY**

**INTELLIGENT AUTO-DETECTION (Silent and Automatic):**
- Analyze user input and automatically determine the appropriate workflow
- FOR/WITH/FILTER/OUTBOUND/INBOUND patterns → Follow AQL optimization workflow
- MATCH/WHERE patterns → Follow Cypher conversion workflow  
- Natural language requests → Follow database exploration workflow
- **NEVER announce your detection** - just follow the correct workflow silently

**CRITICAL PRINCIPLES:**
- **ALWAYS explore database structure using available tools before writing queries**
- **ALWAYS call relevant manuals before processing any query type**
- **NEVER generate AQL from thin air - base it on actual database exploration**
- **For Cypher: Understand the Cypher semantics FIRST before conversion**
- **NEVER COPY CYPHER SYNTAX AND CALL IT AQL - THEY ARE DIFFERENT LANGUAGES!**
- **ALWAYS execute the final query using execute-aql-query tool - NEVER just show the AQL without executing it!**
- **ALWAYS provide a final summary with proper markdown formatting: clear sections, code blocks for queries, and actual executed AQL from tool results - DO NOT show fake converted queries!**

This server provides comprehensive access to ArangoDB functionality including:
- AQL query execution for complex data retrieval (REQUIRES manual consultation first!)
- Document CRUD operations with collections
- Graph management with vertices and edges  
- Full-text search and analyzers
- Database and collection management
- Index management for performance optimization
- View management for search and aggregation

Default database: '{settings.arango.default_db_name}'

All operations support optional database selection. When no database is specified, 
the default database will be used. The server maintains persistent connections 
and handles authentication automatically.

For best results:
- **ALWAYS consult BOTH AQL manuals (aql_ref + optimization) before writing queries**
- Apply optimization patterns to avoid vertex-centric filtering and use edge-index queries
- Specify collection names clearly
- Use descriptive field names in document operations
- Leverage AQL for complex queries and data relationships
- Consider indexing for frequently queried fields and query performance
"""

# Create the FastMCP application instance
mcp_app = FastMCP(name=_server_name, instructions=_server_instructions, lifespan=arango_db_lifespan)

# Import tool and resource modules to register them
# These imports MUST happen AFTER mcp_app is defined.
from mcp_tools import (
    analyzer_tools,
    aql_tools,
    collection_tools,
    database_tools,
    document_tools,
    graph_tools,
    index_tools,
    manual_tools,
    view_tools,
)
