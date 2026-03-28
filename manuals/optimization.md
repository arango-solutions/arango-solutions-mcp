# Graph Query Optimization Guide

## Replacing Vertex-Centric Filtering with Edge Index Queries

Graph queries often need to find edges with certain properties for specific vertices. A common anti-pattern is vertex-centric filtering, where the query iterates over vertices and then checks each connected edge for a condition. This approach effectively scans edges for every vertex, which can be inefficient. Instead, you should detect such patterns and rewrite them to directly filter the edge collection using indexes.

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

Before rewriting, check what indexes exist on the edge collection. Using the MCP tool (for example, a hypothetical LIST INDEX Edges command), confirm if there is an index on the relevant edge property or a composite index with `_from`/`_to`. All ArangoDB edge collections have a built-in index on `_from` and `_to`, and you can add a persistent index on additional fields (like type). If such an index is present, the rewritten query can use it to quickly find matching edges. If an index is missing and the filter is selective, consider advising the creation of a suitable index.

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

Rewriting vertex-centric patterns to edge-centric queries yields fewer iterations and leverages indexes better. The database performs a single indexed scan over edges with the given criteria, rather than an index lookup per vertex followed by filtering. This can significantly speed up query performance, especially in graphs where vertices have many edges but only a few edges meet the condition.

In summary, filter on edges first whenever you detect that a query is filtering edge properties per vertex – it will reduce workload and utilize indexes that are designed for such lookups.