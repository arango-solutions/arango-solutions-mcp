from mcp.server.fastmcp import FastMCP

from arango_connector import arango_db_lifespan
from config import settings

# ============================================================================
# MAIN PROMPT - Read This First
# ============================================================================

_MAIN_PROMPT = """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   🎯 ARANGODB MCP SERVER - WORKFLOW SYSTEM                       ║
║                                                                  ║
║   This server has MANDATORY WORKFLOWS for different tasks       ║
║   You MUST identify the task and follow its workflow            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

## 🚦 TASK DETECTION & WORKFLOW SELECTION

| User Says | Follow This Workflow |
|-----------|---------------------|
| "optimize this query" / "make faster" / "improve performance" | ⬇️ QUERY_OPTIMIZATION_WORKFLOW |
| Provides Cypher (MATCH/WHERE syntax) | ⬇️ CYPHER_CONVERSION_WORKFLOW |
| "show collections" / "explore data" / natural language query | ⬇️ DATABASE_EXPLORATION_WORKFLOW |
| Provides AQL query to execute | ⬇️ AQL_EXECUTION_WORKFLOW |

## ⚠️ CRITICAL RULES

1. **Identify the task type** from user request
2. **Scroll down and read the FULL workflow** for that task
3. **Follow EVERY step** in order - no shortcuts allowed
4. **Gather evidence** at each step
5. **Provide data-driven recommendations** with proof

🚨 IF YOU SKIP STEPS: You are providing guesses, not data-driven results!

## 📚 Detailed workflows are below ⬇️ - scroll down and read the one you need!

"""

# ============================================================================
# SUB-PROMPT 1: Query Optimization Workflow
# ============================================================================

_QUERY_OPTIMIZATION_WORKFLOW = """
═══════════════════════════════════════════════════════════════════
🔧 QUERY OPTIMIZATION WORKFLOW (6 MANDATORY STEPS)
═══════════════════════════════════════════════════════════════════

**WHEN TO USE:** User asks "optimize this query" / "make this faster" / "improve performance"

**YOU ARE HERE:** You detected an optimization request
**WHAT TO DO:** Follow ALL 6 steps below in exact order

⛔ DO NOT:
- Jump to compare-aql-queries without profiling first
- Skip profiling the original query
- Create optimized queries without data
- Make assumptions about performance

✅ YOU MUST DO:

┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: GET KNOWLEDGE FIRST (Learn before doing)               │
└─────────────────────────────────────────────────────────────────┘

**Actions:**
1. Call `get-aql-manual` with manual_name="optimization"
   → Learn optimization patterns (edge-first vs vertex-first, indexes)
   
2. Call `get-aql-manual` with manual_name="aql_ref"  
   → Understand AQL syntax and functions

**Evidence to collect:** Note key patterns from manuals


┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: BASELINE THE ORIGINAL (Understand current performance) │
└─────────────────────────────────────────────────────────────────┘

**Actions:**
1. Call `execute-aql-query` with ORIGINAL query
   → Verify it works, see results, note execution time
   
2. Call `profile-aql-query` with ORIGINAL query
   → Get detailed metrics: time, memory, indexes used, bottlenecks

**Evidence to collect:**
- Execution time (seconds)
- Memory usage (bytes)
- Indexes used
- Documents scanned
- Bottlenecks identified


┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: EXPLORE DATABASE (Know your data)                      │
└─────────────────────────────────────────────────────────────────┘

**Actions:**
1. Call `list-collections`
   → See all collections
   
2. For each collection in query: `get-collection-properties`
   → Get document counts (small vs large)
   
3. For each collection in query: `list-indexes`
   → See available indexes, check if they match filter fields

**Evidence to collect:**
- Collection document counts
- Available indexes (type and fields)
- Missing indexes


┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: ANALYZE & CREATE OPTIMIZED VERSION                     │
└─────────────────────────────────────────────────────────────────┘

**Actions:**
1. Analyze data from Steps 1-3:
   - Match bottlenecks to optimization patterns
   - Check filter selectivity
   - Evaluate collection sizes
   - Identify missing indexes
   
2. Create optimized query based on:
   - Profile bottlenecks
   - Manual patterns
   - Available indexes
   - Collection sizes

**Decision criteria:**
- Edge-first IF: edge filters selective + large vertex collection
- Vertex-first IF: vertex filters selective + small collection
- Combine filters to leverage composite indexes
- Use DOCUMENT() for 1:1 lookups
- Add LIMIT early for existence checks


┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: VALIDATE OPTIMIZATION (Prove it works)                 │
└─────────────────────────────────────────────────────────────────┘

**Actions:**
1. Call `explain-aql-query` on optimized query
   → Preview execution plan, verify index usage
   
2. Call `compare-aql-queries` with:
   - Original query
   - Optimized query
   → Get side-by-side performance comparison

**Evidence to collect:**
- Execution time comparison
- Memory usage comparison
- Index usage comparison
- Actual performance improvement (%)


┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: REPORT WITH EVIDENCE                                   │
└─────────────────────────────────────────────────────────────────┘

**Actions:**
1. Provide comprehensive report with:

   **Original Performance:** (from Step 2)
   - Time, memory, indexes, bottlenecks
   
   **Database Analysis:** (from Step 3)
   - Collection sizes, available indexes
   
   **Optimization Strategy:** (from Step 4)
   - What changed and WHY (reference manual)
   - Which bottlenecks addressed
   
   **Performance Comparison:** (from Step 5)
   - Side-by-side metrics
   - Actual speedup %
   
   **Recommendation:**
   - Which query to use with evidence
   - Indexes to create if needed

2. If needed: Call `create-index` to recommend indexes

🚨 IF YOU SKIP ANY STEP: You are providing guesses, not data-driven optimization!

═══════════════════════════════════════════════════════════════════
"""

# ============================================================================
# SUB-PROMPT 2: Cypher Conversion Workflow
# ============================================================================

_CYPHER_CONVERSION_WORKFLOW = """
═══════════════════════════════════════════════════════════════════
🔄 CYPHER CONVERSION WORKFLOW (7 MANDATORY STEPS)
═══════════════════════════════════════════════════════════════════

**WHEN TO USE:** User provides Cypher query (MATCH/WHERE/RETURN syntax)

**DETECTION:** Look for MATCH, WHERE, RETURN keywords (NOT FOR/FILTER)

⛔ DO NOT:
- Copy Cypher syntax and call it AQL
- Skip understanding Cypher semantics first
- Write AQL without exploring database structure
- Show converted query without executing it

✅ YOU MUST DO:

┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: UNDERSTAND CYPHER SYNTAX                               │
└─────────────────────────────────────────────────────────────────┘

Call `get-aql-manual` with manual_name="cypher2aql"
→ Learn Cypher-to-AQL translation patterns


┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: ANALYZE THE CYPHER QUERY                               │
└─────────────────────────────────────────────────────────────────┘

Understand what the Cypher query does:
- What variables/nodes are used?
- What relationships/patterns exist?
- What conditions are being checked?
- What is the query trying to achieve?


┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: EXPLORE DATABASE STRUCTURE                             │
└─────────────────────────────────────────────────────────────────┘

Use database tools:
- `list-collections` → See available collections
- `list-graphs` → See graph structures
- `read-documents-with-filter` → Sample data


┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: LEARN AQL SYNTAX                                       │
└─────────────────────────────────────────────────────────────────┘

Call `get-aql-manual` with manual_name="aql_ref"
→ Understand AQL syntax (FOR/FILTER/RETURN)


┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: LEARN OPTIMIZATION PATTERNS                            │
└─────────────────────────────────────────────────────────────────┘

Call `get-aql-manual` with manual_name="optimization"
→ Learn how to write performant AQL


┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: CONVERT TO ACTUAL AQL                                  │
└─────────────────────────────────────────────────────────────────┘

Transform Cypher to AQL:
- MATCH → FOR ... IN collection
- Relationships → FOR ... IN OUTBOUND/INBOUND
- WHERE → FILTER
- RETURN → RETURN

**CRITICAL:** Cypher and AQL are COMPLETELY DIFFERENT languages!
DO NOT copy Cypher syntax!


┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: EXECUTE THE CONVERTED AQL (MANDATORY!)                 │
└─────────────────────────────────────────────────────────────────┘

Call `execute-aql-query` with the converted AQL
→ DO NOT just show the AQL - EXECUTE IT!

Then provide summary:
```markdown
## Cypher Conversion Summary

### Original Cypher:
[code block with original]

### Converted AQL:
[code block with ACTUAL executed AQL]

### Results:
[show execution results]
```

**CRITICAL SYNTAX CONVERSION RULES:**
- CYPHER: MATCH (a:Label) -[:Relation]-> (b) WHERE conditions RETURN
- AQL: FOR a IN collection FILTER conditions FOR b IN OUTBOUND a edges RETURN
- DO NOT COPY CYPHER AND CALL IT AQL - they are DIFFERENT languages!

═══════════════════════════════════════════════════════════════════
"""

# ============================================================================
# SUB-PROMPT 3: Database Exploration Workflow
# ============================================================================

_DATABASE_EXPLORATION_WORKFLOW = """
═══════════════════════════════════════════════════════════════════
🔍 DATABASE EXPLORATION WORKFLOW
═══════════════════════════════════════════════════════════════════

**WHEN TO USE:** User asks "what data exists" / "show collections" / "explore database" / natural language queries

**WORKFLOW:**

1. **EXPLORE DATABASE STRUCTURE:**
   - `list-databases` → Available databases
   - `list-collections` → Available collections
   - `list-graphs` → Graph structures

2. **EXAMINE COLLECTIONS:**
   - `get-collection-properties` → Document counts, size
   - `list-indexes` → Indexes on collection
   - `read-documents-with-filter` → Sample documents

3. **CHECK GRAPH STRUCTURES:**
   - `list-graphs` → Graph definitions
   - Check edge collections with `list-indexes`

4. **REVIEW SEARCH CAPABILITIES:**
   - `list-views` → Search views
   - `list-analyzers` → Text analyzers

5. **FOR NATURAL LANGUAGE QUERIES:**
   - Explore database structure (steps 1-4)
   - Call `get-aql-manual` with manual_name="aql_ref"
   - Call `get-aql-manual` with manual_name="optimization"
   - Create informed AQL based on actual structure
   - Execute with `execute-aql-query`
   - Provide summary with query and results

**Provide organized summary** of database structure

═══════════════════════════════════════════════════════════════════
"""

# ============================================================================
# SUB-PROMPT 4: AQL Execution Workflow
# ============================================================================

_AQL_EXECUTION_WORKFLOW = """
═══════════════════════════════════════════════════════════════════
▶️ AQL EXECUTION WORKFLOW
═══════════════════════════════════════════════════════════════════

**WHEN TO USE:** User provides a complete AQL query to execute (not optimize)

**WORKFLOW:**

1. **VALIDATE:** Check if query syntax looks correct
2. **EXECUTE:** Use `execute-aql-query` tool to run the query
3. **RETURN RESULTS:** Provide query results to user

Simple and straightforward - just execute and return results.

═══════════════════════════════════════════════════════════════════
"""

# ============================================================================
# TOOL REMINDERS (add to tool descriptions)
# ============================================================================

_TOOL_REMINDER_PROFILE = """
⚠️ OPTIMIZATION WORKFLOW - STEP 2 CHECK:
✓ Completed Step 1 (get-aql-manual x2)?
If NO → STOP! If YES → Proceed (Step 2 of 6)
"""

_TOOL_REMINDER_COMPARE = """
⚠️ OPTIMIZATION WORKFLOW - STEP 5 CHECK:
✓ Completed Steps 1-4 (manuals + profile + explore + optimize)?
If NO → STOP! If YES → Proceed (Step 5 of 6)
"""

_TOOL_REMINDER_EXPLAIN = """
⚠️ OPTIMIZATION WORKFLOW - STEP 5a CHECK:
✓ Completed Steps 1-4 (manuals + profile + explore + optimize)?
If NO → STOP! If YES → Proceed (Step 5a of 6)
"""

_TOOL_REMINDER_EXECUTE = """
📍 Optimizing a query? This should be Step 2a (baseline execution).
Have you called get-aql-manual first? If not, stop and get manuals.
"""

# ============================================================================
# COMBINE ALL PROMPTS
# ============================================================================

_server_name = "ArangoDB_MCP_Server"
_server_instructions = f"""
{_MAIN_PROMPT}

{_QUERY_OPTIMIZATION_WORKFLOW}

{_CYPHER_CONVERSION_WORKFLOW}

{_DATABASE_EXPLORATION_WORKFLOW}

{_AQL_EXECUTION_WORKFLOW}

═══════════════════════════════════════════════════════════════════
🛠️ SERVER CAPABILITIES
═══════════════════════════════════════════════════════════════════

This server provides comprehensive ArangoDB functionality:

**Query Operations:**
- AQL query execution and optimization
- Query performance profiling (profile, compare, explain)
- Cypher to AQL conversion

**Data Operations:**
- Document CRUD operations with collections
- Bulk document operations

**Graph Operations:**
- Graph management (vertices, edges, traversals)
- Named graph creation and management
- Edge relationship operations

**Search & Analysis:**
- Full-text search with views and analyzers
- Custom analyzer creation
- View management for search and aggregation

**Database Management:**
- Database and collection management
- Index management for performance tuning
- Collection property inspection

**Default Database:** '{settings.arango.default_db_name}'

All operations support optional database selection. When no database is specified, 
the default database will be used. The server maintains persistent connections 
and handles authentication automatically.

**For Best Results:**
- Follow the workflow for your task type (see above)
- Consult manuals before writing queries
- Use profiling tools for optimization decisions
- Explore database structure before creating queries
- Provide evidence-based recommendations with data
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
    query_profiler_tools,
    view_tools,
)
