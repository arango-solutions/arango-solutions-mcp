# Graph Query Optimization Guide

---

# 🚨 MANDATORY 6-STEP OPTIMIZATION WORKFLOW 🚨

## ⛔ CRITICAL: NEVER SKIP THESE STEPS WHEN OPTIMIZING QUERIES ⛔

**When a user requests query optimization, you MUST follow this EXACT workflow:**

### STEP 1: Read Manuals (ALWAYS FIRST - NON-NEGOTIABLE)
```
1. Call: get-aql-manual(manual_name="aql_ref")
2. Call: get-aql-manual(manual_name="optimization")
3. Study both manuals before proceeding to Step 2
```
**⚠️ Without Step 1, you will create syntactically incorrect or poorly optimized queries!**

### STEP 2: Profile Original Query (MANDATORY - DO NOT SKIP)
```
Call: profile-aql-query(aql_query=<ORIGINAL_USER_QUERY>)

Analyze the results:
- Execution time (seconds)
- Peak memory usage (bytes)
- Indexes used (or NOT used)
- Documents scanned (full scan vs index scan)
- Bottlenecks identified
```
**⚠️ Without Step 2, you have NO baseline to measure improvement!**

### STEP 3: Explore Database Structure (MANDATORY - DO NOT SKIP)
```
1. Call: list-collections()
2. For each collection in query:
   Call: get-collection-properties(collection_name=...)
3. For each collection in query:
   Call: list-indexes(collection_name=...)

Analyze:
- Collection sizes (document counts)
- Filter selectivity (% of documents matching filters)
- Available indexes (types, fields, unique, sparse)
- Missing indexes that could improve performance
```
**⚠️ Without Step 3, you cannot make informed optimization decisions!**

### STEP 4: Create Optimized Query
```
Based on Steps 2 & 3 data:
1. Apply optimization patterns from this manual
2. Consider index availability
3. Evaluate filter selectivity
4. Combine filters where beneficial
5. Use AGGREGATE instead of nested subqueries
6. Document WHY each change was made
```

### STEP 5: Verify Optimization (MANDATORY - DO NOT SKIP)
```
Option A (PREFERRED):
Call: compare-aql-queries(queries=[
  {"name": "Original", "query": <original>},
  {"name": "Optimized", "query": <optimized>}
])

Option B (if execution not possible):
Call: explain-aql-query(aql_query=<optimized>)

Verify:
- Optimized is actually FASTER than original
- Memory usage improved or acceptable
- Correct indexes are being used
- Results are equivalent
```
**⚠️ Without Step 5, your "optimization" may make performance WORSE!**

### STEP 6: Provide Recommendations
```
Show:
- Comparison results (execution time, memory)
- Performance improvement (X% faster, Y% less memory)
- Index recommendations (create missing indexes)
- Further optimization opportunities
- Explain why optimization works
```

---

## 🔴 ENFORCEMENT RULES 🔴

1. **DETECTION**: If user message contains:
   - "optimize query" / "optimize the below query" / "improve query"
   - "make query faster" / "query performance" / "slow query"
   - AND contains AQL keywords (FOR, FILTER, RETURN, COLLECT)
   
   → **TRIGGER THE 6-STEP WORKFLOW AUTOMATICALLY**

2. **NEVER** skip Steps 2, 3, or 5 - these are data-driven validation steps

3. **NEVER** create "optimized" queries based only on patterns without profiling data

4. **NEVER** provide optimization recommendations without comparison/explain results

5. **ALWAYS** explain which step you're on and why you're doing it

---

## ⚠️ CRITICAL: Context-Dependent Optimization

**This guide describes ONE optimization pattern, but it is NOT always the right choice!**

Before applying any optimization:
1. ✅ Use `list-collections` to check collection sizes
2. ✅ Use `get-collection-properties` to analyze document counts
3. ✅ Use `list-indexes` to verify available indexes
4. ✅ Analyze filter selectivity (what % of data matches filters?)
5. ✅ Test query performance before and after optimization

## Decision Framework: When to Apply This Pattern

### Use Starting-with-Edge Approach When:
- ✅ Edge filters are highly selective (< 1% of edges match)
- ✅ Vertex collection is very large (> 100K documents)
- ✅ Good indexes exist on edge properties
- ✅ Large result sets expected
- ✅ Graph is densely connected (many edges per vertex)

### Keep Starting-with-Vertex Approach When:
- ✅ Vertex filters are highly selective (< 1% of vertices match)
- ✅ Small result sets or early termination possible
- ✅ Vertex collection is small (< 10K documents)
- ✅ Edge collection is huge without good indexes
- ✅ Query returns no data (short-circuits quickly)

### Always Use AQL EXPLAIN and Profiling Tools
Reference: From `index_utilization.txt` - Use `db._explain(query)` or `stmt.explain()` to compare execution plans and see which indexes will be used.

**MCP Tools Available:**
- `profile-aql-query` - Execute query with full performance profiling (timing, memory, indexes used)
- `compare-aql-queries` - Compare multiple query variations side-by-side
- `explain-aql-query` - Get execution plan without executing the query

---

## Replacing Vertex-Centric Filtering with Edge Index Queries

Graph queries often need to find edges with certain properties for specific vertices. In some scenarios, iterating over vertices and then checking each connected edge for a condition can be inefficient. This approach effectively scans edges for every vertex. When appropriate (see Decision Framework above), you should rewrite queries to directly filter the edge collection using indexes.

**Note:** This pattern is beneficial mainly when edge filtering is selective and vertex collections are large.

### Recognize the Pattern

Look for queries that loop through vertices and within that loop filter edges by some property or condition. For example, a query might do:

```aql
FOR v IN Vertices
  FOR e IN Edges
    FILTER e._from == v._id AND e.type == "friend"
    RETURN v
```

In this pseudo-AQL, the inner loop filters edges by type for each vertex v. This is vertex-centric because it centers on each vertex and then checks edges.

### Why It's Suboptimal

Scanning an edge collection for each vertex multiplies work. Even if the database has a default edge index on `_from`/`_to` for fast neighbor lookup, the above pattern still retrieves all edges for each vertex and then filters them in memory. In other words, it finds the list of edges for a vertex quickly, but then still iterates through those edges to test the condition. This per-vertex iteration adds overhead.

### Use Edge Indexes Directly

Instead of vertex-centric loops, flip the approach to an edge-centric filter. Most graph databases (e.g., ArangoDB) index edges by their endpoints (source/target), and you can create combined indexes on an endpoint plus other attributes for fast lookups. Leverage these indexes by querying the edge collection directly with the desired edge property filter (and the vertex ID if needed). This way, the database can jump straight to the relevant edges via the index, rather than scanning per vertex. For instance, if an index exists on the edge attribute (or a composite index on `_from` and that attribute), you can rewrite the query as:

```aql
FOR e IN Edges
  FILTER e.type == "friend"
  LET v = DOCUMENT(Vertices, e._from)
  RETURN v
```

Here we filter the Edges collection by the type attribute upfront. The database will use an index on `Edges.type` (or a combined `_from+type` index) to retrieve only "friend" edges, regardless of the vertex. If you only need edges for a specific vertex, include that in the filter as well (e.g. `FILTER e._from == @vertexId AND e.type == "friend"`). By querying edges in one go through an index, we avoid repeated edge scans and drastically reduce the workload.

### Verify Index Availability

Before rewriting, check what indexes exist on the edge collection using `list-indexes` MCP tool. 

**Built-in Indexes:**
- All edge collections automatically have an edge index on `_from` and `_to`

**Additional Indexes to Consider:**
- Persistent index on edge attributes (e.g., `["type"]`)
- **Vertex-Centric Index**: A special persistent index combining `_from`/`_to` with edge attributes

### Vertex-Centric Indexes (Official ArangoDB Feature)

From the official documentation (`vertex-centric-index.txt`):

**What are Vertex-Centric Indexes?**
Persistent indexes that index a combination of a vertex (`_from` or `_to`) as the first field, followed by edge attributes. These are specifically designed for graphs with **supernodes** (vertices with exceptionally high numbers of edges).

**When to Use:**
- Graphs contain supernodes (vertices with many edges)
- You filter on edge properties during graph traversals
- Pattern matching queries with edge filters

**Example Creation:**
```javascript
// For OUTBOUND traversals - index _from first
db.edgeCollection.ensureIndex({ 
  type: "persistent", 
  fields: ["_from", "type"] 
});

// For INBOUND traversals - index _to first
db.edgeCollection.ensureIndex({ 
  type: "persistent", 
  fields: ["_to", "type"] 
});
```

**How They Work:**
Instead of finding all edges for a vertex then filtering in memory, vertex-centric indexes allow finding edges matching BOTH the vertex AND edge condition in one index lookup.

**Example Query That Benefits:**
```aql
FOR v, e, p IN 3..5 OUTBOUND @start GRAPH @graphName
  FILTER p.edges[*].type ALL == "friend"
  RETURN v
```

Or direct edge collection iteration:
```aql
FOR edge IN edgeCollection
  FILTER edge._from == "vertices/123456" AND edge.type == "friend"
  RETURN edge
```

**Note:** The optimizer may choose the built-in edge index over vertex-centric indexes based on cost estimates, even if vertex-centric might be faster in practice.

## Example Optimization

### Before (vertex-centric filtering)

The query below finds all vertices that have an outgoing "friend" edge. It does so by iterating every vertex and checking its edges:

```aql
FOR v IN Vertices
  FILTER LENGTH(
    FOR e IN Edges
      FILTER e._from == v._id AND e.type == "friend"
      LIMIT 1  /* only need to know if at least one exists */
      RETURN e
  ) > 0
  RETURN v
```

This approach will examine the edges of each vertex one by one. It’s inefficient if many vertices exist, because it performs a lot of repeated edge lookups.

### After (edge-index filtering)

We can rewrite the query to target the edge collection first, using an index on the Edges by type (and implicitly `_from` or `_to` if narrowing direction). For example:

```aql
/* Get all vertices that have a "friend" edge */
FOR e IN Edges
  FILTER e.type == "friend"
  COLLECT vertId = e._from INTO group
  /* Now fetch the vertex documents (if needed) */
  LET v = DOCUMENT(Vertices, vertId)
  RETURN v
```

This version scans the Edges collection just once for "friend" edges, using an index on the type field to retrieve them efficiently. We then collect the unique `_from` vertex IDs and fetch those vertices. The result is the same set of vertices, but the query avoids an outer loop over every vertex. By using the edge index, the database directly finds edges of type "friend" for each relevant vertex, instead of iterating through each vertex's edge list.

## Benefits

Rewriting queries to filter edges first (when appropriate - see Decision Framework above) yields fewer iterations and leverages indexes better. The database performs a single indexed scan over edges with the given criteria, rather than an index lookup per vertex followed by filtering. This can significantly speed up query performance, especially in graphs where vertices have many edges but only a few edges meet the condition.

**Important:** This pattern is most effective when:
1. Edge filtering is selective (< 1% of edges match)
2. Vertex collection is large (many vertices to iterate)
3. Appropriate indexes exist on edge properties

---

## Index Utilization Best Practices

From official documentation (`index_utilization.txt`):

### Troubleshooting Query Performance

**Use EXPLAIN to verify index usage:**
```javascript
var query = "FOR doc IN collection FILTER doc.value > 42 RETURN doc";
db._explain(query);
```

**Common reasons indexes are NOT used:**
1. Attribute names misspelled (schema-free = no error messages)
2. No suitable index exists on filtered attributes
3. Index only works with comparison operators: `==`, `<`, `<=`, `>`, `>=`, `IN`
4. Index attribute used in function or expression: `TO_NUMBER(doc.value) == 42` ❌
5. Sparse indexes not used when optimizer detects possible `null` values

### Composite Index Usage Rules

For a composite index on `["value1", "value2"]`, it can be used for:

**Single attribute conditions:**
```aql
FILTER doc.value1 == ...
FILTER doc.value1 > ...
FILTER doc.value1 IN ...
```

**Multiple attribute conditions (order matters):**
```aql
FILTER doc.value1 == ... && doc.value2 == ...
FILTER doc.value1 == ... && doc.value2 > ...
FILTER doc.value1 == ... && doc.value2 IN ...
```

**Cannot use index for:**
```aql
FILTER doc.value2 == ...  // ❌ Second attribute alone
```

**Algorithm:** Index attributes are checked left-to-right. If a condition uses `==` or `IN`, the next attribute is considered. Otherwise, remaining attributes are not used.

### Multiple Indexes and OR Conditions

Queries can use multiple indexes when using logical OR:
```aql
FOR doc IN collection 
  FILTER doc.value1 == 42 || doc.value2 == 23 
  RETURN doc
```
This requires separate indexes on `value1` and `value2`.

---

## Summary

This optimization pattern (starting with edge collection) is ONE tool in your optimization toolkit. Success depends on:

1. **Data characteristics**: Collection sizes, filter selectivity, graph density
2. **Index availability**: Proper indexes on filtered attributes
3. **Query patterns**: Whether vertex or edge filtering is more selective
4. **Testing**: Always use EXPLAIN and compare actual performance

**Remember:** The "best" query structure depends on your specific data and use case. Test both approaches!