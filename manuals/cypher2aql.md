# Manual: Translating Cypher Graph Queries to ArangoDB AQL Queries

**Introduction:**
This manual is intended for a large language model (LLM) that needs to translate Neo4j Cypher graph queries into ArangoDB AQL queries. It complements the official ArangoDB AQL documentation by focusing on *how to perform correct and optimized translations from Cypher to AQL*. The context is cybersecurity and network management graphs, so examples will use entities like **Device**, **User**, **Event**, **Connection**, etc. The goal is to preserve the semantics of Cypher queries while using ArangoDB’s document/graph model efficiently.

**Scope:**
We will cover differences in data models and terminology, one-to-one syntax mappings (with examples), translation patterns for common Cypher clauses (MATCH, WHERE, RETURN, OPTIONAL MATCH, etc.), graph traversal and edge direction handling, equivalent functions and expressions, common pitfalls to avoid, and optimization tips specific to ArangoDB’s query execution. Best practices for representing Cypher’s graph concepts in ArangoDB’s model are also included.

---

## 1. Data Model Differences: Neo4j vs ArangoDB Graphs

Before translating queries, understand the fundamental differences between Neo4j’s Property Graph model (accessed via Cypher) and ArangoDB’s multi-model approach (accessed via AQL):

* **Neo4j (Cypher)** uses a *labeled property graph* model: data is stored as nodes and relationships. Nodes can have one or more **labels** (types/categories) and properties (key-value pairs). Relationships connect two nodes, have a **relationship type**, a direction, and can also hold properties. The graph is schema-less in the sense that new labels or relationship types can be introduced on the fly.

* **ArangoDB (AQL)** is a multi-model database (supports documents, key-value, graphs, etc.). Graphs in ArangoDB are stored using **collections** of documents for vertices and **collections** of documents for edges. Each vertex or edge is a JSON document with a unique primary key. Edges use special attributes `_from` and `_to` to refer to the connected vertices’ `_id` values. AQL can query across different models in one query, but for graph traversal it uses a specific syntax with the `FOR ... IN ...` construct. Graphs must be defined upfront or referenced by specifying relevant collections.

**Key Terminology Mapping:** The table below compares equivalent or similar concepts between ArangoDB’s AQL and Cypher:

| **ArangoDB (AQL)**                                          | **Neo4j (Cypher)**                         |
| ----------------------------------------------------------- | ------------------------------------------ |
| **Document** (vertex or edge JSON document with properties) | **Node** (vertex with properties)          |
| **Vertex** (document in a vertex collection)                | **Node** (graph node)                      |
| **Edge** (document in an edge collection)                   | **Relationship** (edge between nodes)      |
| **Document collection** (stores vertices of a given type)   | **Label** (label grouping nodes)           |
| **Edge collection** (stores edges of a given type)          | **Relationship type** (type of edge)       |
| **Attribute** (document field)                              | **Property** (node/relationship field)     |
| **\_key** / **\_id** (unique document key / id)             | **Internal ID** (Neo4j’s internal node id) |
| **Graph** (named graph with vertex/edge collections)        | **Database** (graph database instance)     |
| **Depth / Hops** (traversal steps)                          | **Hops** (length of a path)                |
| **Array** (list data type)                                  | **List** (collection data type)            |
| **Object** (JSON object/document)                           | **Map** (property map data type)           |

**Node labels vs Collections:** In Neo4j, a node can have multiple labels, and you can match a node by any of its labels or combinations. In ArangoDB, a document belongs to exactly one collection (which acts like a single “label”). There is no direct equivalent of multiple labels on one document – you would either use multiple collections or include a list of “types/labels” as a field in the document and filter on it. When translating, assume that each Cypher label corresponds to an ArangoDB collection for simplicity. (If a Cypher query uses multiple labels on a node, the LLM should either translate it to a filter on a type field or note that the Arango data model needs adjustment, since Arango cannot automatically query a document by multiple collections.)

**Edge relationships:** In Neo4j, relationships are stored inherently and always connect two nodes with a direction. In ArangoDB, edges are stored as separate documents in an **edge collection**, with `_from` and `_to` attributes pointing to vertices. An edge’s “type” is implicitly the edge collection name (or a property if you use one edge collection for multiple types). Thus, a Neo4j relationship type is analogous to an Arango edge collection. If Neo4j uses relationships with properties, Arango edges can also have arbitrary extra attributes (since edges are JSON docs) – those can be queried or returned as needed.

**Graph definition:** In Neo4j, you do not explicitly define a schema; you can just start using a new label or relationship. In ArangoDB, you should create collections (and define a **Graph** in Arango if using named graph features) before inserting data. The existence of collections and edge definitions is assumed when translating queries. Also, ArangoDB allows secondary indexes on document fields to optimize lookups (which you should leverage for properties used in FILTERs, similar to creating indexes on node properties in Neo4j for faster MATCH).

**Identity and Keys:** Neo4j’s `ID()` function returns a node’s internal id (an integer) and nodes can also have a property that serves as an external ID. ArangoDB documents have a unique string `_id` (format `"CollectionName/Key"`) and a user-assigned `_key` (unique within the collection). When translating, if a Cypher query uses `id(n)` or relies on node identity, the equivalent in AQL is usually using the document’s `_id` or `_key`. For example, to return an identifier, you might return `vertex._key` or the full `_id` depending on context.

**Example:** Suppose we have a simple network graph. In Neo4j, you might have nodes labeled `Device` and `User`, with a relationship `CONNECTED_TO` between devices and `USES` between a user and a device. In ArangoDB, you would have a collection **Device**, a collection **User**, and edge collections **connected\_to** (edges between Device documents) and **uses** (edges from User to Device). Before querying, these collections must be created and populated. Each Device or User is a document with attributes (e.g., `name`, `ip`, etc.), and each edge is a document with `_from` and `_to` (and possibly attributes like timestamp or status).

---

## 2. Core Query Syntax: Cypher vs AQL

Cypher and AQL are both declarative, but their syntax is different. **Cypher** focuses on pattern matching with ASCII-art notation inside `MATCH` and other clauses, whereas **AQL** uses a composable syntax with **FOR loops, filters, and transformations**. Here is a quick comparison of key query constructs in Cypher and their AQL equivalents:

| **Cypher Clause/Keyword**                            | **AQL Clause/Keyword**                              | **Notes**                                                                                          |
| ---------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `MATCH (pattern) ... RETURN ...`                     | `FOR ... IN ... RETURN ...`                         | Basic reading query. In AQL the pattern is expressed via traversals or joins inside the FOR loop.  |
| `WHERE` (filter condition)                           | `FILTER` (condition)                                | Used after a FOR loop to filter results.                                                           |
| `RETURN` (projection output)                         | `RETURN` (projection expression)                    | Similar purpose. AQL returns JSON values (objects, arrays, etc.).                                  |
| `ORDER BY` (sort results)                            | `SORT` (sort results)                               | Syntax differs (`SORT field ASC/DESC`).                                                            |
| `LIMIT n [OFFSET m]`                                 | `LIMIT [offset,] n`                                 | AQL uses `LIMIT count` or `LIMIT offset, count`. Cypher uses `SKIP m LIMIT n` for offset.          |
| `UNWIND` (list unwinding)                            | `FOR ... IN` (iterate list)                         | AQL’s FOR can iterate over array values to unwind lists (Cypher’s UNWIND).                         |
| Pattern direction `(-->)`                            | Traversal direction `OUTBOUND`                      | `OUTBOUND` follows `_from -> _to` direction (edge from A to B).                                    |
| Pattern direction `(<--)`                            | Traversal direction `INBOUND`                       | `INBOUND` goes reverse (edges pointing into the vertex).                                           |
| Undirected `(--)"`                                   | Traversal direction `ANY`                           | `ANY` ignores edge direction (traverse both ways).                                                 |
| `CREATE` (node or relationship)                      | `INSERT ... INTO` (collection)                      | Used to insert new documents (vertices or edges) in AQL.                                           |
| `SET` (update properties)                            | `UPDATE ... IN` (collection)                        | Update specific fields in AQL (partial update).                                                    |
| *(No direct Cypher equivalent, MERGE covers upsert)* | `UPSERT ... INSERT ... UPDATE ...`                  | AQL’s upsert (optional if MERGE semantics needed).                                                 |
| `DELETE` (node or relationship)                      | `REMOVE ... IN` (collection)                        | Remove documents in AQL (edges or vertices).                                                       |
| `OPTIONAL MATCH`                                     | *No single keyword* – use subquery or other pattern | Achieve via a subquery and `LET` to handle missing optional data (explained later).                |
| `shortestPath()` function                            | `SHORTEST_PATH` traversal                           | AQL has a shortest path traversal construct for paths.                                             |

**Note on Direction:** In Cypher, you indicate edge direction with arrows in the ASCII art pattern. For example, `(a)-[:REL]->(b)` means an outgoing relationship from `a` to `b`, while `(a)<-[:REL]-(b)` is incoming to `a`, and `(a)-[:REL]-(b)` means either direction (undirected match). In AQL, you do *not* draw patterns but instead specify direction keywords. For instance, `OUTBOUND` corresponds to `-->`, `INBOUND` to `<--`, and `ANY` to `--` (no arrow). This means when translating, you must correctly choose `OUTBOUND` or `INBOUND` based on the Cypher pattern orientation, or `ANY` if the Cypher pattern doesn’t enforce direction.

**General Query Form:** A basic AQL query for graph data often looks like:

```aql
FOR <vertexVar> [, <edgeVar>, <pathVar>]
    IN <depthSpec> <direction> <startVertex> <edgeCollectionOrGraph>
    [FILTER conditions]
    [COLLECT or SORT ...]
    RETURN <projection>
```

This single `FOR ... IN` construct can replace a combination of Cypher’s `MATCH` (with pattern), and subsequent `WHERE`/`RETURN`. AQL’s graph traversal can cover variable-length path patterns in one go, whereas fixed-length patterns might be translated into multiple nested loops or a specific range of depth. We will break down specific translations next.

---

## 3. Matching Nodes and Basic Patterns

#### 3.1 Selecting Nodes by Label and Property

**Cypher:** To find nodes of a given label with certain property conditions, Cypher uses `MATCH (alias:Label { prop: value, ... })`. For example:

```cypher
MATCH (d:Device {hostname: "router1"})
RETURN d;
```

This finds a `Device` node with hostname “router1”.

**AQL:** Use a `FOR` loop over the corresponding collection, and a `FILTER` for the property condition:

```js
FOR d IN Device
  FILTER d.hostname == "router1"
  RETURN d
```

This will iterate over the **Device** collection and return the document(s) whose `hostname` equals "router1". The result will be the JSON document(s) representing the device(s).

**Notes:**

* Ensure you use the correct collection name for the label (e.g., `Device` collection for `:Device` label).
* If the Cypher pattern had multiple property conditions inside `{...}`, include all in the AQL `FILTER` with the appropriate logical AND/OR. For instance, `{status: "active", ip: "10.0.0.5"}` becomes `FILTER d.status == "active" AND d.ip == "10.0.0.5"`.
* If the Cypher uses just a label without properties (e.g., `MATCH (u:User) RETURN u` to get all users), the AQL is simply `FOR u IN User RETURN u` (you can add `LIMIT` if needed to avoid huge outputs). This will return all documents in the **User** collection.

#### 3.2 Matching a Single Edge (1-hop relationship)

**Cypher:** Pattern matching of one relationship looks like:

```cypher
MATCH (u:User)-[r:USES]->(d:Device)
WHERE u.name = "Alice"
RETURN u, d;
```

This finds pairs of user and device where the user `Alice` *USES* a device. `r` here is the relationship, which we might include if we need relationship properties.

**AQL:** There are a couple of ways to translate a single hop pattern. The most direct is to use a **graph traversal** in AQL:

```js
FOR u IN User
  FILTER u.name == "Alice"
  FOR d IN OUTBOUND u uses   // traverse outgoing "uses" edge from user to device
  RETURN { user: u, device: d }
```

Here:

* `OUTBOUND u uses` goes from the `u` vertex out along the **uses** edge collection to the connected vertex `d`. This corresponds to `(u)-[:USES]->(d)`.
* We return an object with both the user and device. We could also return `u, d` separately, but returning a combined object or a specific projection is often clearer in JSON (the LLM can decide format based on needs).

Alternatively, one can explicitly join the collections without using the graph traversal syntax:

```js
FOR u IN User
  FILTER u.name == "Alice"
  FOR rel IN uses
    FILTER rel._from == u._id
    FOR d IN Device
      FILTER d._id == rel._to
      RETURN { user: u, device: d }
```

This does the same thing in a more manual way:

* It finds the user(s) named "Alice",
* then finds any edge document in the **uses** edge collection where that user is the `_from`,
* then finds the device document pointed to by `_to`.

Both approaches yield the same result, but the first (traversal) is more succinct and lets ArangoDB optimize using its edge index. The traversal form is recommended for graph patterns.

If the relationship was undirected in Cypher (e.g. `(a)-[r:CONNECTED]-(b)` meaning either direction is okay), you would use `ANY` instead of OUTBOUND/INBOUND in AQL:

```js
FOR a IN Device
  FILTER a.name == "X"
  FOR b IN ANY a connected_to
  RETURN b
```

This finds devices connected to device X regardless of direction. Ensure that the edge collection `connected_to` is defined appropriately (possibly edges in both directions or treat as undirected conceptually).

**Including Relationship Properties:** If the Cypher query returns or filters on relationship `r` (e.g., `r.timestamp`), in AQL you should capture the edge in the traversal. The traversal syntax allows two variables: one for the vertex and one for the edge. For example:

```js
FOR u IN User
  FILTER u.name == "Alice"
  FOR d, rel IN OUTBOUND u uses
    FILTER rel.role == "admin"
    RETURN { user: u.name, device: d.name, accessLevel: rel.role }
```

This would correspond to a Cypher pattern `(u:User)-[rel:USES]->(d:Device) WHERE u.name="Alice" AND rel.role="admin" RETURN u.name, d.name, rel.role`.

#### 3.3 Chaining Multiple Hops (Fixed-length paths)

Cypher can express a path of length 2 (two hops) like:

```cypher
MATCH (u:User)-[:USES]->(d:Device)-[:CONNECTED_TO]->(d2:Device)
RETURN u.name, d2.ip;
```

This finds all second-hop devices `d2` that are connected to a device `d` that a user `u` uses.

In AQL, you can simply nest the FOR loops or traversals:

```js
FOR u IN User
  FOR d IN OUTBOUND u uses
    FOR d2 IN OUTBOUND d connected_to
      RETURN { user: u.name, secondHopDevice: d2.ip }
```

This mirrors the pattern: first hop via **uses** edge, second hop via **connected\_to** edge. Each FOR picks up where the last left off. You can add `FILTER` clauses at any level if the query has conditions on intermediate nodes or relationships. For example, if the Cypher had `WHERE d.status = "online"`, you’d add `FILTER d.status == "online"` in the middle of the nested loops.

This explicit chaining works but can get verbose for many hops. It is equivalent to a traversal of a certain depth as we’ll see next. If the pattern is linear and you know the exact length (like 2 hops), nesting is fine. If it’s variable or long, AQL’s range syntax may be cleaner.

#### 3.4 Variable-Length Traversals (Cypher `*` notation)

Cypher allows variable-length patterns, e.g. `-[:CONNECTED*1..3]->` means 1 to 3 hops, and `-[:CONNECTED*]->` means any number of hops (no limit). For example:

```cypher
MATCH (d:Device {ip: "10.0.0.1"})-[:CONNECTED*1..3]->(other:Device)
RETURN other.hostname;
```

This finds devices within 3 hops of the device with IP 10.0.0.1.

**AQL:** Use the `min..max` depth syntax in the traversal:

```js
FOR start IN Device
  FILTER start.ip == "10.0.0.1"
  FOR other IN 1..3 OUTBOUND start connected_to
    RETURN other.hostname
```

This will traverse between 1 and 3 hops away from the `start` device along the **connected\_to** edges, returning each reachable device’s hostname. If you want to include direct neighbors and up to 3 hops out, this matches the Cypher `*1..3` range.

Important differences:

* **Unlimited depth:** Cypher’s `*` without an upper bound means “traverse to any depth until no further matches”. AQL **does not support an unbounded traversal** directly. You *must* specify a max depth. If you truly need “any depth”, you can set a high number or restructure the query (but be cautious: extremely deep traversals can be expensive or even infinite if cycles exist). Often in practice, a reasonable max is chosen based on domain knowledge.
* **Including starting node:** Cypher patterns typically don’t include the starting node as a match unless specified with 0 hops (`*0..`). In AQL, the default min depth is 1, but you can set a min of 0 if you want to include the start vertex itself as a result. For example, `FOR v IN 0..3 OUTBOUND start ...` would include depths 0,1,2,3 – depth 0 returning the start device itself. This corresponds to Cypher’s ability to have 0-length paths (like `(:Device)-[*0..3]->(target)` where target could be the same as the start in the 0-hop case).

**Filtering during traversal:** If there are conditions on intermediate nodes or edges in a variable-length pattern, you can use `FILTER` inside the loop, but note that it will filter the *resulting vertices* not necessarily prune paths. AQL provides a `PRUNE` clause to stop exploring certain branches. For instance, to emulate a condition like `MATCH (d:Device)-[:CONNECTED*..]->(x:Device {os: "Linux"})`, you might need to check the property at the last hop. Using `FILTER x.os == "Linux"` after the traversal will filter final results, but still explores all paths. If you want to cut off traversal when a condition fails, `PRUNE` is used. This is advanced usage: for translation basics, applying a FILTER on the traversed vertex is usually sufficient, but keep in mind it doesn’t prevent exploring that vertex’s neighbors unless using prune.

**Example (with cybersecurity context):** Consider a query: “Find all devices that a given compromised device can reach within 2 hops.” In Cypher:

```cypher
MATCH (d:Device {status:"compromised"})-[:CONNECTED*1..2]->(target:Device)
RETURN target.name;
```

AQL:

```js
FOR d IN Device
  FILTER d.status == "compromised"
  FOR target IN 1..2 OUTBOUND d connected_to
    RETURN target.name
```

This will list device names that are 1 or 2 hops away from any compromised device. (If you only wanted from a specific device by ID or IP, filter `d` accordingly.)

---

## 4. Filtering and Constraints (WHERE vs FILTER)

The Cypher `WHERE` clause translates to AQL `FILTER` conditions. Key points:

* **Placement:** In Cypher, `WHERE` can appear after a MATCH to filter on nodes/relationships from that pattern. In AQL, you place `FILTER` after the relevant `FOR` where the variable is introduced. Ordering is flexible as long as it’s after the `FOR` and before using the variable in RETURN or further traversal.

* **Logical operators:** Use `AND`, `OR`, `NOT` in AQL, similar to Cypher’s `AND`, `OR`, `NOT` (or the older `AND`, `OR`, `NOT` keywords in Cypher).

* **Comparison operators:** AQL uses `==` for equality and `!=` for inequality (Cypher uses `=` for equality, `<>` or `!=` for inequality). Greater/less than are the same symbols. Check for nulls accordingly (see below).

* **String matching:** Cypher’s `=~` (regex), `STARTS WITH`, `ENDS WITH`, `CONTAINS` map to AQL’s string functions or operators:

  * Regex `=~` can be done with AQL’s `=~` operator (AQL supports regex matching operator as well).
  * `STARTS WITH "prefix"` -> use `LIKE(prefix% )` or `SUBSTRING` check: e.g. `FILTER LIKE(name, "prefix%", true)` for case-insensitive, or `FILTER POSITION(name, "prefix") == 0` (position 0 means starts with).
  * `CONTAINS(substring)` -> AQL doesn’t have a direct `CONTAINS` function for strings, but you can use `LIKE("%substring%")` or `POSITION(name, substring)` to see if the substring occurs (returns index or -1).
  * `ENDS WITH "suffix"` -> check ending via `SUBSTRING(name, LENGTH(name)-LENGTH("suffix"), LENGTH("suffix")) == "suffix"` or use `LIKE("%suffix")`.

  For example, `WHERE u.email ENDS WITH "@example.com"` in Cypher would translate to:

  ```js
  FILTER LIKE(u.email, "%@example.com")
  ```

  (This is case-sensitive by default; add `, true` as third arg in `LIKE` for case-insensitive.)

* **Property existence:** In Cypher, `exists(n.prop)` returns true if the property is present (and in newer versions `n.prop IS NOT NULL` is used to check existence because Neo4j treats missing as null). In AQL, you can check existence explicitly with the function `HAS(doc, "prop")`. However, usually you can also do `doc.prop != null` to check that the property is not null **or not present** (if a property is missing, accessing it yields `null` in AQL). Be cautious: `HAS(doc,"x")` returns true even if the value is `null` (since the key exists). If you need to ensure the property exists and is not null, you might combine checks. For translation, if Cypher uses `exists(n.prop)`, a safe approach is `FILTER HAS(n, "prop")` to mimic existence regardless of value.

* **NULL handling:** Neo4j’s null logic differs since a missing property is null but certain comparisons might behave differently. In AQL, comparing to `null` works: e.g., `FILTER n.prop == null` will be true for both missing or explicitly null properties. So `WHERE n.prop IS NULL` in Cypher can be `FILTER n.prop == null` in AQL, and `WHERE n.prop IS NOT NULL` can be `FILTER n.prop != null` (or use `HAS` if you strictly want existence as mentioned).

**Example:**
Cypher: `MATCH (e:Event) WHERE e.severity > 3 AND e.type = "malware" RETURN e`

```cypher
MATCH (e:Event)
WHERE e.severity > 3 AND e.type = "malware"
RETURN e;
```

AQL:

```js
FOR e IN Event
  FILTER e.severity > 3 AND e.type == "malware"
  RETURN e
```

This filters events with severity > 3 and type exactly "malware". Make sure to use `==` for equality.

**Optional Pattern Filtering:** If a `WHERE` in Cypher is attached to an `OPTIONAL MATCH` pattern, it behaves differently (it will filter the optional part, not the whole result). In AQL, since we handle optional matches via subqueries (see next section), any filtering on the optional part should be inside that subquery.

---

## 5. Returning Results and Projections

Cypher’s `RETURN` clause can return nodes, relationships, paths, or specific properties, and also allows transforming outputs (aliases, function results, etc.). AQL’s `RETURN` is more like returning an expression or constructing a JSON value for each result row.

**Returning entire documents vs specific fields:**

* In Cypher, `RETURN n` returns the whole node with all its properties (in Neo4j browser it shows a node object). In AQL, `RETURN vertex` returns the entire document (including internal `_id`, `_key`, etc., and all properties). This is usually fine – it will be a JSON object in the result. If you only need certain fields, you can project an object with just those fields to reduce output.
* You can create new objects on the fly: e.g., `RETURN {name: d.name, ip: d.ip}` will output a JSON like `{"name": "...", "ip": "..."}` for each result. This is equivalent to Cypher’s capability to return maps like `RETURN {name: d.name, ip: d.ip}`.
* Use **aliases** or **AS** in Cypher to name outputs. In AQL, you don’t explicitly alias in the RETURN clause, but you can name fields in an object. If you just return a value, the result has no named field (just the value). For consistent output structure, it’s often good to return an object.

**Returning multiple variables:** Cypher can return multiple columns, e.g. `RETURN u.name, d.ip`. AQL can return a single compound result per iteration. Typically we pack values into an object (or an array). For example:

```js
RETURN { user: u.name, deviceIP: d.ip }
```

This is analogous to `RETURN u.name AS user, d.ip AS deviceIP` in Cypher. The keys `user` and `deviceIP` become the JSON keys in output.

**Paths:** If Cypher returns a path variable `p`, the LLM should translate it only if needed. In AQL, if you used a traversal with a `path` variable (the third variable in `FOR ... IN`), you can return `path` which is an object with `vertices` and `edges` arrays. For example `RETURN p` would give a structure containing the list of vertices and edges in the path. If you only need the nodes from the path, you could return `p.vertices`. If just need their names: `p.vertices[*].name` (using list comprehension syntax in AQL to map each vertex to its name). However, returning entire paths is less common in typical translations unless explicitly requested.

**Aggregations and group projections:** This will be covered in Section 7, but note that Cypher returns aggregates as single values or grouped values. AQL’s `COLLECT` or `COLLECT AGGREGATE` clause can produce similar outputs but might need constructing objects in RETURN to match Cypher’s format.

**Example projection:**
Cypher: `MATCH (u:User)-[:USES]->(d:Device) RETURN u.name, collect(d.ip) AS devices`
– This returns each user’s name and a list of IPs of devices they use.
We will discuss how to translate `collect()` in AQL later (it involves grouping). But the output format in AQL would likely be constructed as `{ user: u.name, devices: deviceList }`.

For now, simple returns one-to-one with the traversal are straightforward by returning objects or values.

---

## 6. OPTIONAL MATCH and Left Joins

Cypher’s `OPTIONAL MATCH` tries to match a pattern and, if the pattern is not found, uses `NULL` for the missing parts instead of dropping the result. It’s essentially a left outer join on pattern existence. There is no direct `OPTIONAL MATCH` keyword in AQL, but we can achieve similar behavior with subqueries or conditional logic.

**Translation strategy:**

1. **Basic approach – subquery with `FIRST`**: Run a subquery to fetch the optional part, and use `LET` to capture the result (or null if none). The `FIRST()` function is handy because it returns the first element of a subquery, or `null` if the subquery returns empty.
2. Ensure the main query (outer loop) always yields a result for each main item, even if the optional part is missing (hence defaulting to null).

**Example:** “List all devices and their owner user if one exists.” Suppose `OWNED_BY` is a relationship from User to Device (a device may or may not have an owning user). In Cypher:

```cypher
MATCH (d:Device)
OPTIONAL MATCH (d)<-[:OWNED_BY]-(u:User)
RETURN d.name, u.name;
```

This returns device name and owner name (or `null` for u.name if no owner).

**AQL Translation:**

```js
FOR d IN Device
  LET u = FIRST(
    FOR user IN User
      FOR e IN owns   // 'owns' is the edge collection for OWNS/OWNED_BY
        FILTER e._from == user._id AND e._to == d._id
        RETURN user
  )
  RETURN { device: d.name, owner: u != null ? u.name : null }
```

Let’s break this down:

* We iterate over all devices `FOR d IN Device`.
* We use a subquery to find a user connected via the owns edge:

  * `FOR user IN User ... FILTER e._from == user._id AND e._to == d._id ... RETURN user` finds all users that own this device `d`.
  * Wrapping it with `FIRST(... RETURN user)` means we only take the first such user if any (if multiple owners are possible, this will pick one arbitrarily; for a one-to-one relation, it’s fine).
  * If no user owns the device, the subquery returns empty, and `FIRST()` will give `null`.
* We assign that to `u`. If `u` is not null, we use `u.name`, otherwise null, in the returned object.

The result is a list of `{ device: "..", owner: ".." }` objects. If a device has no owner, `"owner": null`.

**Simpler approach using traversal:** Alternatively, if an edge collection connects Device to User in the opposite direction (Device -> User or User -> Device), you could do a traversal that might yield zero results. However, a direct traversal in AQL (like `FOR u IN INBOUND d owns RETURN u`) inside the main loop won’t emit anything if none exists – meaning the outer result would be lost. That’s why the subquery with `LET` is used: it ensures the outer `d` is preserved even if the inner finds nothing.

In fact, the above can be simplified if we know `owns` edges are from User to Device (like `_from: User, _to: Device`). Then:

```js
FOR d IN Device
  LET u = FIRST(FOR u IN INBOUND d owns RETURN u)
  RETURN { device: d.name, owner: u != null ? u.name : null }
```

This does the same: `INBOUND d owns` traverses any incoming “owns” edge to find a `u`. If none, the subquery yields empty and FIRST gives null. This is more succinct (one FOR inside FIRST rather than two), but functionally equivalent. The Stack Overflow example for an optional link follows this pattern.

**Multiple optional matches:** If a Cypher query has multiple OPTIONAL MATCH parts attaching different optional data, you can do multiple subqueries, each with its own LET variable. Each one adds a potential null field if not found. Be mindful that each subquery is an independent lookup, so performance can be a consideration (but Arango’s optimizer might handle some efficiently especially if indexed).

**Ensure correct null usage:** The projection uses a ternary (`?:`) operator or an `IF` function implicitly with `u != null ? u.name : null` to avoid accessing `u.name` when `u` is null (which would error). The LLM should include this check or use AQL’s safe navigation if it existed (AQL doesn’t have optional chaining, so explicit check is needed as above).

**Optional relationship existence (no new data needed):** Sometimes, Cypher’s OPTIONAL MATCH is used just to check if something exists (and maybe filter based on that). For example, “find devices that have no connections” could be done as:

```cypher
MATCH (d:Device)
OPTIONAL MATCH (d)-[:CONNECTED]->(x)
WHERE x IS NULL
RETURN d;
```

In AQL, this can be translated by using a subquery to check existence:

```js
FOR d IN Device
  LET anyConn = FIRST(FOR x IN OUTBOUND d connected_to RETURN 1)
  FILTER anyConn == null
  RETURN d
```

Here `anyConn` will be `1` if an outbound connection exists (since the subquery returns at least one 1), or `null` if none. Filtering `== null` keeps only devices with no outgoing connection. (We could similarly check inbound if needed or both directions using ANY).

**Summary:** Use `LET var = FIRST(subquery)` for optional matches. It’s a robust pattern to ensure the outer results aren’t lost when the optional part is missing. The LLM should be careful to place any subsequent FILTER on the optional part outside the subquery appropriately, or inside if the filter pertains only to the optional pattern.

---

## 7. Aggregation, Grouping, and Ordering

Aggregations in Cypher (like `COUNT`, `SUM`, `AVG`, `COLLECT`, etc.) have their counterparts in AQL, but AQL’s syntax is a bit different, often using the `COLLECT` keyword.

#### 7.1 Simple Aggregates (no grouping)

If you just need an aggregate on all results:

* Cypher example: `MATCH (e:Event) RETURN COUNT(e)` – count all Event nodes.

* AQL ways:

  1. Use `COLLECT AGGREGATE` without grouping:

     ```js
     FOR e IN Event
       COLLECT AGGREGATE total = COUNT(e)
       RETURN total
     ```

     This will return an array with one number (the total count).
  2. Use a shortcut: `RETURN LENGTH(Event)` which directly returns the number of documents in the Event collection. (AQL’s `LENGTH(<collection>)` gives the count of documents in that collection.) This is simpler for a full count. For other aggregates like sum, avg, use the COLLECT AGGREGATE form or an alternative.
  3. Another approach for count: `RETURN COUNT(FOR e IN Event RETURN 1)` – this is a trick to count via a subquery. The simplest is the `COLLECT AGGREGATE` shown or `LENGTH()`.

* Cypher example: `MATCH (e:Event) RETURN AVG(e.severity)` – average of a property.

* AQL:

  ```js
  FOR e IN Event
    COLLECT AGGREGATE avgSeverity = AVG(e.severity)
    RETURN avgSeverity
  ```

  This yields the average (or null if none). You can wrap it with `ROUND()` or other functions as needed (as shown in Arango docs for rounding average). If you only need a single number, that’s fine. If you want to return other things as well, see grouping.

AQL’s `COLLECT AGGREGATE` essentially folds the entire preceding results into one group (unless a grouping key is specified) and computes the aggregate(s).

#### 7.2 Grouping by a Key

Cypher implicitly groups by any non-aggregated fields in the RETURN. In AQL, you explicitly specify grouping keys using `COLLECT <keyName> = <expression>` and optionally use `... AGGREGATE name = AGG_FUNC(value)` for aggregates. Alternatively, AQL allows collecting raw results into an array (`INTO`) for post-processing.

**Example:** “Count how many devices each user uses.”
Cypher:

```cypher
MATCH (u:User)-[:USES]->(d:Device)
RETURN u.name AS user, COUNT(d) AS deviceCount;
```

This groups by each user and counts their devices.

AQL:

```js
FOR u IN User
  FOR d IN OUTBOUND u uses
    COLLECT userName = u.name WITH COUNT INTO count
    RETURN { user: userName, deviceCount: count }
```

Explanation:

* We iterate `User` and then their outbound `uses` devices.
* `COLLECT userName = u.name WITH COUNT INTO count` groups by the `u.name`. The `WITH COUNT INTO count` gives the number of items in each group (counting iterations of the loop, effectively counting devices per user).
* We then return an object. `userName` is the grouped key (each unique user name), and `count` is the number of devices. The result will be one object per user who has at least one device, e.g. `{ "user": "Alice", "deviceCount": 3 }`, etc.

This corresponds to Cypher’s grouping by user. If a user had no devices, they wouldn’t appear in this result by default (since our loop only counts those who had at least one). If we needed to include users with count 0, we’d have to handle that by an outer loop of users and optional counting (similar to optional match concept, or use `COLLECT ... INTO` trick with an outer loop).

**Using INTO (collecting values):** AQL can also gather the members of each group:

```js
FOR u IN User
  FOR d IN OUTBOUND u uses
    COLLECT user = u.name INTO devicesList = d.ip
    RETURN { user, devices: devicesList }
```

Here, instead of count, we use `INTO devicesList = d.ip` which collects all `d.ip` values for each user group into an array. This would produce, for example: `{ "user": "Alice", "devices": [ "10.0.0.1", "10.0.0.2" ] }`. This is equivalent to Cypher’s `collect(d.ip)`. The Arango syntax `COLLECT ... INTO var = expression` gives an array of expressions. It’s similar to `COLLECT ... AGGREGATE arr = ARRAY_AGG(expression)` in other databases.

**Multiple aggregates:** You can compute several aggregates in one COLLECT. For example:

```js
FOR e IN Event
  COLLECT type = e.type AGGREGATE avgSev = AVG(e.severity), cnt = COUNT(e)
  RETURN { type, avgSeverity: ROUND(avgSev), count: cnt }
```

This groups events by type and outputs average severity (rounded) and count per type. (Cypher: `MATCH (e:Event) RETURN e.type, avg(e.severity), count(e)`).

#### 7.3 Sorting and Limiting results

Cypher uses `ORDER BY ... ASC/DESC` and `LIMIT`. In AQL:

* Use `SORT <expr> ASC/DESC` after your FOR (and before COLLECT if you want to sort raw data, or after COLLECT if sorting grouped output).
* If you only want top N or with offset, use `LIMIT` clause. Example: `SORT count DESC LIMIT 5` to get top 5.
* Note: If you used `COLLECT` for grouping, you might need to apply `SORT` after the COLLECT (because grouping yields a new set of results). AQL allows a `SORT` after a COLLECT in the query.

Example:

```js
FOR u IN User
  FOR d IN OUTBOUND u uses
    COLLECT user = u.name WITH COUNT INTO deviceCount
    SORT deviceCount DESC
    LIMIT 5
    RETURN { user, deviceCount }
```

This returns the top 5 users with the most devices, sorted by count descending. In Cypher that might be:

```cypher
MATCH (u:User)-[:USES]->(d:Device)
RETURN u.name, COUNT(d) AS deviceCount
ORDER BY deviceCount DESC
LIMIT 5;
```

The logic is analogous.

**Aggregation pitfalls:**

* Make sure to group by the correct variable. In AQL, grouping by `u.name` was safe assuming names uniquely identify users. If not, you might group by `u._key` or `u` (the entire document or its id) to truly group per user, and then still return `u.name` as a field. For example, `COLLECT user = u INTO grouped = d` groups by the *entire user object* (not allowed directly) or better `COLLECT userId = u._id INTO devices = d` to group by unique id. The specifics depend on whether the grouping key is unique or not. The LLM should be mindful: if Cypher is grouping by a node itself (like `RETURN u, count(d)`), you might want to collect by `u._id` (to group per node) and still return `u` (one representative document perhaps via `ANY(grouped)` or via the fact you can include non-aggregated values if using `KEEP` in collect, but that’s advanced).
* In simpler terms: If grouping by a node, use its unique identifier in COLLECT.

**ArangoDB’s approach vs Cypher:** Cypher allows aggregation in the return without explicit grouping of other columns. Arango requires explicit group or aggregate for each value:

* If you forget to COLLECT and try to `RETURN u.name, COUNT(d)` directly in AQL, it will error because AQL doesn’t allow aggregate functions outside a COLLECT (except in subqueries).
* So always use `COLLECT ... AGGREGATE ...` or `COLLECT ... WITH COUNT` when translating a Cypher aggregation.

---

## 8. Graph Traversals and Path Queries

Thus far we used simple traversals for neighbors or fixed hops. ArangoDB AQL can do more complex traversals and even find shortest paths or enumerate paths. Cypher has built-in predicates like `shortestPath()` and can explore paths as well.

#### 8.1 Directed vs Undirected Traversal in Detail

We covered that `OUTBOUND`, `INBOUND`, `ANY` control edge direction in AQL. When translating:

* A pattern like `(a)-[:REL]->(b)` becomes `FOR b IN OUTBOUND a RelCollection ...`.
* `(a)<-[:REL]-(b)` becomes `FOR b IN INBOUND a RelCollection ...` (or do `OUTBOUND b RelCollection` after getting `b` if reversing perspective, but usually stick to one direction per traversal).
* An undirected pattern `(a)-[:REL]-(b)` in Cypher should be `ANY` in AQL, *or* you can model it by using two traversals if needed. However, using `ANY` is straightforward as long as the edge collection is specified (it will traverse from the start vertex following both \_from and \_to).

**Be careful**: If the Cypher query doesn’t explicitly specify direction (like just `(x)--(y)`), it finds relationships of any direction between x and y. In AQL, `ANY` will do that. But ensure the edge collection allows that or is defined appropriately. If the graph is undirected logically, often edges are stored one way and you use ANY to get neighbors either way.

#### 8.2 Variable Depth and Path Enumeration

Cypher can return paths or check for patterns of variable length. In AQL:

* If you need to return a **path** (sequence of vertices/edges), you can use the `path` variable in the traversal. For example:

  ```js
  FOR v, e, p IN 2..4 OUTBOUND startVertex Connected
    RETURN p
  ```

  would return path objects of lengths 2 to 4. Each path object `p` has `p.vertices` and `p.edges` arrays. You might format them as needed (e.g., `RETURN p.vertices[*].name` to get the names along each path).

* If Cypher uses something like `[n IN nodes(p) | n.id]` to project path, you can similarly use list comprehensions on `p.vertices` in AQL.

* **All paths vs any path**: Cypher by default with variable length will find all paths satisfying the pattern (up to length, with possible repeats unless prevented). AQL’s traversal will also find all reachable vertices (you can get distinct vertices or even request distinct paths if needed via options). By default, Arango might not return duplicate vertices along different paths unless you use the `path` variable.

* **Avoiding cycles**: Arango’s traversal avoids revisiting nodes by default in a single traversal (it has a default uniqueness constraint on vertices along a path). Cypher can revisit nodes in longer patterns unless you explicitly prevent it. Generally, the translations will naturally avoid infinite loops, but be aware if a Cypher pattern allowed revisiting and you need to mimic that (Arango allows control via OPTIONS like `uniqueVertices`). The default is usually to not revisit the same vertex on the same path.

#### 8.3 Shortest Path Queries

Neo4j Cypher provides the `shortestPath()` function to find *a* shortest path between two nodes, and `allShortestPaths()` for all equal-length shortest paths. ArangoDB’s AQL has a built-in traversal for shortest paths.

**Example:** Find the shortest connection path between two devices in the network.
Cypher:

```cypher
MATCH (a:Device {ip: "192.168.1.1"}), (b:Device {ip: "10.0.0.5"}),
  p = shortestPath((a)-[:CONNECTED*]-(b))
RETURN [n IN nodes(p) | n.hostname] AS pathHosts;
```

This finds one shortest path (any direction) between device A and B and returns the sequence of hostnames in that path.

AQL:

```js
LET start = FIRST(FOR v IN Device FILTER v.ip == "192.168.1.1" RETURN v._id)
LET goal = FIRST(FOR v IN Device FILTER v.ip == "10.0.0.5" RETURN v._id)

FOR v IN ANY SHORTEST_PATH start TO goal connected_to
  RETURN v.hostname
```

**Explanation:**

* We determine the start and target vertices’ IDs (assuming we only know them by property IP). We used subqueries with `FIRST` to get the `_id` of the devices with those IPs. If they are guaranteed to exist, fine; if not, the result might be empty (which is similar to Cypher not finding a node).
* The `FOR v IN ANY SHORTEST_PATH start TO goal connected_to` uses Arango’s shortest path finder. `ANY` means consider edges in both directions (like an undirected path) – which matches the Cypher pattern `-* -` (no direction specified, allowing reversal mid-path). If your connections should be treated as undirected for path length, use `ANY`. If you know the path must follow directed edges in one direction, use `OUTBOUND` or `INBOUND` accordingly.
* This traversal yields each vertex on the shortest path in order (the loop will iterate over the vertices along the shortest path). We then RETURN `v.hostname` for each vertex, meaning the query result will be an array of hostnames from start to end representing the path.
* The result might look like: `[ "Router-A", "Switch-5", "Firewall", "Server-X" ]` – including both the start and end device names in sequence.

This corresponds to the Cypher example returning the list of node hostnames.

If we needed to return the whole path as one result (like a single array for the path, not a list of vertices as separate results), we could instead do:

```js
RETURN (
  FOR v IN ANY SHORTEST_PATH start TO goal connected_to
    RETURN v.hostname
)
```

This wraps the traversal in parentheses, which in AQL yields a single array of the `v.hostname` values. So the final result would be `[ ["Router-A", "Switch-5", "Firewall", "Server-X"] ]` (array within array, because AQL always returns an array of results, but you can omit the extra nesting by returning the subquery result directly if it’s top-level).

**All Shortest Paths:** If Cypher’s `allShortestPaths` is needed, Arango has an `ALL_SHORTEST_PATHS` traversal syntax (similar usage but returns all equal-length shortest paths). The LLM can use `ALL SHORTEST_PATH` if multiple shortest paths are desired. Example:

```js
FOR p IN ANY ALL_SHORTEST_PATHS start TO goal connected_to
  RETURN p.vertices[*].hostname
```

This would return multiple paths (each as an array of hostnames). Use this only if required, as it’s more expensive.

**Weighted shortest paths:** Cypher doesn’t directly support weighted shortest path in the basic function (though there are graph algorithms library for that). Arango’s shortest path can consider weights (with `OPTIONS { weightAttribute: "...", defaultWeight: ... }` on edges). If the Cypher query implies a weighted path (not typical unless using algo procedures), you could set those options accordingly in AQL.

**Path existence:** If the Cypher query only cares whether a path exists (like `MATCH (a)-[*]->(b) RETURN exists(p)` or something), in AQL you could do a shortest path and check if any result came, or a traversal with `LIMIT 1` to break early. For example, to just check connectivity, one could do:

```js
LET path = FIRST(
  FOR v IN ANY 1..100 OUTBOUND startVertex connected_to  // depth up to 100 as a big number
    FILTER v._id == goalVertex
    LIMIT 1
    RETURN true
)
RETURN path != null
```

This is a bit contrived; Arango may have a function or there’s a graph function `GRAPH_SHORTEST_PATH` to use in a different way. But essentially, use a traversal or shortest path and see if you got something.

#### 8.4 General Traversal Tips

* **Limiting breadth/depth:** Arango allows a `PRUNE` condition to stop traversing certain branches early (e.g., `PRUNE condition`). If the Cypher query had something like `MATCH (n:Node)-[:REL*..]->(m) WHERE someConditionAlongPath`, sometimes using PRUNE is more efficient than traversing everything and filtering later. E.g., `PRUNE v.status == "inactive"` to stop going further when hitting an inactive node.

* **Unique vs repeated vertices:** By default, AQL traversals have a depth-first search (DFS) order and do not revisit vertices on the same path. You can change to breadth-first with `OPTIONS { order: "bfs" }` if needed (for example, to find shortest paths via traversal by layering, though now we have shortest path built-in). Usually, you don’t need to set this unless you care about traversal order or path enumeration specifics.

* **Graph name vs collection:** If a **named graph** is defined in ArangoDB containing your vertex and edge collections, you can use the `GRAPH "<graphName>"` syntax. For example:

  ```js
  FOR v IN 1..3 OUTBOUND startVertex GRAPH "NetworkGraph" RETURN v
  ```

  Instead of listing edge collections. This uses the set of edge collections associated with that graph. The LLM should know the graph name if provided; otherwise specifying collections works.

* **Multiple edge types in one traversal:** If a Cypher pattern allows multiple relationship types (e.g., `MATCH (a)-[:TYPE1|:TYPE2]->(b)`), you can handle this by listing multiple edge collections in AQL traversal:

  ```js
  FOR b IN OUTBOUND a type1_edges, type2_edges RETURN b
  ```

  This would traverse either edge type. If using a named graph that contains both, just one GRAPH traversal covers it, but if you want to restrict to certain edge collections out of many, listing them or using `FILTER IS_SAME_COLLECTION("Type1Edges", e)` on edge variable are options. The simplest is to specify the set of edge collections in the traversal syntax (anonymous graph traversal).

---

## 9. Translating Functions and Expressions

Cypher has many built-in functions (string, numeric, date, list operations). ArangoDB AQL provides similar functionality, though names differ. Below are some common ones and their equivalents:

* **String case:** `toLower(str)` in Cypher -> `LOWER(str)` in AQL. `toUpper(str)` -> `UPPER(str)`.

* **Substring:** `substring(str, start, length)` in Cypher -> `SUBSTRING(str, start, length)` in AQL. Also AQL has `LEFT(str, n)` and `RIGHT(str, n)`.

* **Length of string or list:** `size(str)` or `length(str)` in Cypher for string length -> `LENGTH(str)` in AQL. Likewise, `size(list)` -> `LENGTH(list)`. (AQL’s LENGTH works on strings, arrays, and even objects (number of keys) or collection as mentioned.)

* **List operations:** Cypher list indexing `[i]` can be done with `[i]` in AQL if you have an array. Many Cypher list functions (head, last, tail, etc.) can be done with array indices or slicing in AQL. For example, Cypher `head(list)` -> AQL `list[0]`, `last(list)` -> `list[-1]` (AQL supports negative index from end).

* **List comprehension:** Cypher `[x IN list WHERE condition | expr]` translates to AQL list comprehension: `FOR x IN list FILTER condition RETURN expr` (often used inside a `[...]`). Actually, AQL doesn’t have a direct inline list comprehension syntax except via a subquery return. But you can produce an array using a subquery in RETURN or even use the AQL array function `ARRAY()` with a FOR inside it. Simpler:

  ```js
  RETURN (
    FOR x IN list
      FILTER <condition>
      RETURN <expr>
  )
  ```

  This yields the filtered/transformed list.

* **Mathematical functions:** Cypher’s `abs()`, `ceil()`, `floor()`, `round()` -> AQL has `ABS()`, `CEIL()`, `FLOOR()`, `ROUND()` (as demonstrated earlier for rounding avg).

* **Datetime:** Neo4j has date types and functions, Arango stores dates typically as strings or timestamps and has date functions like `DATE_NOW()`, `DATE_FORMAT()` etc. If Cypher uses something like `date()` or timestamp, you might need to ensure the data model. Possibly out of scope unless needed.

* **Type conversion:** Cypher’s toInteger, toFloat, toString -> AQL will automatically cast in many cases or has functions like `TO_NUMBER()`, `TO_STRING()`, etc.

* **NULL coalescing:** Cypher’s `coalesce(expr1, expr2, ...)` returns first non-null. In AQL, you can simulate this with the logical OR operator because of how it handles truthy/falsy: e.g., `expr1 || expr2` will return expr1 if it’s not null/false/empty, otherwise expr2. Be careful, `0` or empty string are falsy too, so this might skip them. Alternatively, AQL has no direct coalesce function, but you can use the ternary operator: `expr1 != null ? expr1 : expr2`. For multiple, nest it. There is also a function `NVL(val, default)` that returns default if val is null (similar to coalesce for two arguments).

* **Existential subquery:** Cypher’s `EXISTS{ MATCH ... }` can be translated to a subquery that returns a boolean. E.g., `FILTER LENGTH(FOR ... RETURN 1) > 0` to simulate existence. Or simply use `ANY` with a subquery.

* **ID and labels:**

  * `id(n)` -> as mentioned, use `n._id` or `n._key` depending on what’s needed. There’s also `HAS()` for existence which we covered, and if needed, `ATTRIBUTES(n)` to get all property keys (like Cypher’s `keys(n)`).
  * `labels(n)` (list of labels) – since Arango doesn’t have labels, if the data model has a field for type or labels, you would return that. Otherwise, if each collection corresponds to one label, you can return an array with that label (or multiple if you encoded multi-labels in a field).

* **Relationships:**

  * `type(rel)` in Cypher returns the relationship type name. In Arango, since each edge knows its collection via `_id` (“EdgeCollection/Key”), you can extract the collection name. One way is the function `PARSE_IDENTIFIER(rel)._collection` which gives the collection name of a given id. Or if you know which edge collections you traversed, you implicitly know the type. If needed, you can include a static string or the edge collection in the output.

* **Pattern predicates:** Cypher has `exists( (n)-[:REL]->() )` to check if a relationship of a type exists for a node. In AQL, this is done with an `INBOUND`/`OUTBOUND` traversal of depth 1 and checking if any result exists (like the optional match example earlier where we filtered by absence or presence).

**Example conversions:**

* Cypher: `RETURN toUpper(u.name)` -> AQL: `RETURN UPPER(u.name)`.

* Cypher: `RETURN substring(d.ip, 0, 7)` -> AQL: `RETURN SUBSTRING(d.ip, 0, 7)`.

* Cypher: `WHERE n.name STARTS WITH "A"` -> AQL: `FILTER LIKE(n.name, "A%", true)` (the `true` for case-insensitive if needed).

* Cypher: `RETURN size((d)--())` (number of connections of a node d). Arango doesn’t have a direct `size((d)--())`, but you can do:

  ```js
  LET deg = LENGTH(FOR x IN ANY d connected_to RETURN 1)
  RETURN deg
  ```

  This uses a subquery to count any neighbors (ANY direction) of d. If you only want out-degree or in-degree, use OUTBOUND or INBOUND.

* Cypher: `FILTER x IN list WHERE x.age > 30` within a comprehension or clause. In AQL, within a subquery: `FOR x IN list FILTER x.age > 30 RETURN x`.

* Cypher’s conditional `CASE ... WHEN ... THEN ... ELSE ... END` -> AQL has ternary `(condition ? trueExpr : falseExpr)`. For multiple conditions, nest or use `SWITCH()` function if needed. But usually ternary is fine.

The LLM should look up specific function names in the provided AQL documentation if an unusual function appears in Cypher. But many are straightforward.

---

## 10. Modifying Data: CREATE, MERGE, SET, DELETE

While the focus is on querying, translations might involve Cypher write clauses. Here’s how to handle them:

* **Creating nodes (Cypher `CREATE (n:Label { props })`):** In AQL, you use `INSERT`:

  ```cypher
  CREATE (d:Device {hostname: "NewRouter", ip: "10.0.0.99"})
  ```

  AQL:

  ```js
  INSERT { hostname: "NewRouter", ip: "10.0.0.99" } INTO Device
  ```

  This will create a new document in the Device collection. Neo4j would auto-generate an ID; in Arango, an `_key` will be auto-generated if not provided. You can supply `_key` if you want a specific one (like using something unique).

* **Creating relationships (Cypher `CREATE (a)-[:RELTYPE]->(b)`):** In Neo4j, you must have `a` and `b` nodes already bound in the query (from a prior MATCH or by creating them). In AQL, you need the `_id` of both documents. Typically, you will have done a FOR loop or subquery to get the documents.
  For example:

  ```cypher
  MATCH (u:User {name:"Bob"}), (d:Device {name:"Laptop"})
  CREATE (u)-[:USES]->(d);
  ```

  AQL:

  ```js
  LET uId = FIRST(FOR u IN User FILTER u.name == "Bob" RETURN u._id)
  LET dId = FIRST(FOR d IN Device FILTER d.name == "Laptop" RETURN d._id)
  INSERT { _from: uId, _to: dId } INTO uses
  ```

  We find the `_id` of Bob and the `_id` of the Laptop, then insert a new edge document into the **uses** collection linking them. If either is not found, those LET variables become null; the INSERT of nulls would fail or create a bad edge. Cypher would not create anything if the MATCH doesn’t find nodes. In AQL you might want to guard against nulls (e.g., only insert if both IDs are not null by adding an `FILTER uId && dId` before insert, or using a subquery).

* **Setting properties (Cypher `SET n.prop = value` or adding properties):** In AQL, use `UPDATE` for partial update or `REPLACE` for full replace.

  ```cypher
  MATCH (d:Device {ip:"10.0.0.1"})
  SET d.status = "offline", d.checkedAt = timestamp();
  ```

  AQL:

  ```js
  FOR d IN Device
    FILTER d.ip == "10.0.0.1"
    UPDATE d WITH { status: "offline", checkedAt: DATE_NOW() } IN Device
  ```

  This finds the device(s) and updates those fields. Unmentioned fields remain unchanged. We used `DATE_NOW()` for a current timestamp (in ms) as equivalent to Cypher’s hypothetical `timestamp()` function. Note that if multiple docs match, this updates all of them (Cypher would also update all matching nodes). If only one expected, perhaps add `LIMIT 1`.

* **MERGE (match or create):** Arango has an `UPSERT`. E.g.,

  ```cypher
  MERGE (u:User {username:"alice"}) ON CREATE SET u.created = timestamp() ON MATCH SET u.lastSeen = timestamp();
  ```

  In AQL, assuming `username` is a key:

  ```js
  UPSERT { username: "alice" }
    INSERT { username: "alice", created: DATE_NOW(), lastSeen: DATE_NOW() }
    UPDATE { lastSeen: DATE_NOW() }
    IN User
  ```

  This tries to find a User with username alice. If not found, it inserts with created & lastSeen. If found, it updates lastSeen. (AQL’s UPSERT uses a search object, an insert object, and an update object.)

  If `username` was the primary key `_key`, we could simply do a regular `INSERT` with `ignoreErrors` option to avoid duplicate key error on conflict, or fetch first then conditionally insert. But UPSERT is straightforward for merge logic.

* **Deleting nodes or edges (Cypher `DELETE`):** In AQL, `REMOVE document IN Collection`.

  ```cypher
  MATCH (d:Device {hostname:"OldRouter"}) DETACH DELETE d;
  ```

  To translate, note Neo4j’s `DETACH DELETE` means delete the node and its relationships. ArangoDB won’t automatically remove connected edges when a vertex is removed (unless you explicitly set up a purge, but generally you must remove edges first or separately). The LLM should attempt to remove edges manually or rely on a graph setting if any. Usually:

  ```js
  FOR d IN Device
    FILTER d.hostname == "OldRouter"
    FOR e IN outbound d connected_to
      REMOVE e IN connected_to
    REMOVE d IN Device
  ```

  This first removes edges from that device to others, then removes the device. If edges can also come inbound, you’d also remove inbound edges similarly (or use `ANY` and handle duplicates carefully). This is more complex than Cypher’s detach delete because Arango does not have a single command to detach.
  If just deleting an edge by itself (Cypher `MATCH (a)-[r:REL]->() DELETE r`), AQL:

  ```js
  FOR r IN RelCollection
    FILTER r._from == aId AND r._to == bId
    REMOVE r IN RelCollection
  ```

  Or if you had the edge document in a variable via traversal, you can `REMOVE rel IN RelCollection`.

* **Updating relationships:** Cypher can `SET r.prop = ...` on a relationship. In AQL, edges are documents, so:

  ```js
  FOR v, r IN OUTBOUND a RelCollection
    FILTER v._id == someCondition
    UPDATE r WITH { prop: newValue } IN RelCollection
  ```

  That finds the edge (via traversal or separately iterating the edge collection) and updates it. Alternatively, you could `FOR r IN RelCollection FILTER r._from == ... AND r._to == ... UPDATE r ...`.

**Important:** AQL modifications (`INSERT`, `UPDATE`, `REMOVE`) cannot be freely mixed with traversal in the same query unless you are careful with usage (AQL requires that a modifying operation is the last thing in a query or you collect results before continuing, etc.). It’s usually fine if you just do them in sequence like shown, but complex mixes require subqueries. The manual context likely doesn’t require heavy focus on this – just ensure the LLM knows how to form the basic insert/update/remove statements correctly in translation.

**Return from writes:** Neo4j’s `CREATE/SET` queries can end with `RETURN` to output the created/updated nodes. In AQL, after an `INSERT` or `UPDATE`, you can use `RETURN NEW` or `RETURN OLD` to get the new or old version of documents. For example, `INSERT ... IN Device LET new = NEW RETURN new`. If translation requires returning created data, the LLM can incorporate that.

---

## 11. Common Pitfalls in Translation

When converting Cypher to AQL, be wary of the following pitfalls and differences:

* **Label vs Collection name mismatches:** Ensure every label in Cypher maps to the correct collection. Typos or case differences will break AQL (ArangoDB is case-sensitive for collection names and attribute names). Also, if multiple labels were used in Cypher, determine how that is represented in Arango (one collection or a type field). The LLM should not assume a label that doesn’t have a corresponding collection; if none, highlight that the query can’t directly translate without data model adjustments.

* **Missing Graph Context:** Cypher can match patterns without explicitly naming which relationship collection because Neo4j inherently knows relationship types. In AQL, you must specify the edge collection or a named graph. If the user hasn’t defined which edge collection corresponds to a given relationship type, the LLM should clarify or pick a logical name. (We assumed e.g. `CONNECTED_TO` relationship corresponds to `connected_to` edge collection, etc.) A wrong edge collection yields incorrect results.

* **Optional match dropping results:** If you attempt to translate an OPTIONAL pattern with a simple traversal, you might inadvertently drop cases where the optional part is absent (because the traversal loop won’t execute). Always use the `LET ... = FIRST(subquery)` method for optional relationships to preserve the outer result. A common mistake is to try something like:

  ```js
  FOR d IN Device
    FOR u IN INBOUND d owns   // if none, no d will be returned at all
    RETURN ...
  ```

  This would exclude devices with no owners entirely. Instead, use a subquery or an `OUTER APPLY` style approach as we did.

* **Over-counting with multiple matches:** If a Cypher query has multiple MATCH clauses (not optional) separated by commas, it means all those patterns must exist and they are combined (like a join). For example `MATCH (u:User), (d:Device) WHERE u.name = d.ownerName RETURN ...` – here it’s a cartesian product filtered by a condition. In AQL, if you use two FOR loops, you’ll automatically get a cartesian product of users and devices, so you *must* include the join condition as a FILTER to mimic Cypher’s behavior (which they did with `WHERE u.name = d.ownerName`). Always replicate those conditions, or else you produce a full cross product incorrectly. In the example, you’d do:

  ```js
  FOR u IN User
    FOR d IN Device
      FILTER u.name == d.ownerName
      RETURN ...
  ```

  If you forget the FILTER, you’d return all combinations of user and device which is wrong.

* **Cartesian products in Cypher:** If Cypher has two unconnected `MATCH` clauses, it intentionally means a cartesian product of those matches. AQL’s nested FOR loops naturally do that product. So that part is fine, but be mindful: large cartesian products can be very heavy in Arango too, so consider if that was really intended.

* **Multiple relationships between the same nodes:** If the graph allows duplicate edges or multiple edges of the same type between nodes, Cypher’s pattern `(a)-[:REL]->(b)` would find all of them unless uniqueness enforced. AQL traversal will also iterate over each distinct edge document. This typically is fine. Just remember that if counting relationships, AQL will count each edge document, matching Cypher’s behavior.

* **Using the correct depth in traversal:** Off-by-one errors – e.g., translating `*1..2` but then using `1..2` correctly (which is inclusive of both 1 and 2 hops, as intended). If you accidentally used `2` (min=2, max=2) you’d miss the 1-hop case. Or using `1..*` which isn’t allowed. Always specify numeric range.

* **No unlimited traversal without max:** As mentioned, AQL needs a max. If the Cypher query truly has no bound, decide on a sensible high bound or inform that it’s not supported. The LLM might say something like “AQL cannot express an unbounded path length; consider using a large max or redesigning the query.”

* **Null and boolean differences:** Cypher may treat null in conditional expressions differently (e.g., `WHERE not exists(n.prop)` vs AQL’s logic). Test those logic translations carefully. AQL’s `== null` catches both undefined and null which is usually what you want if Cypher’s checking missing.

* **Counting vs returning arrays:** Cypher’s `collect()` yields a list which might be used in further operations. In AQL, `COLLECT ... INTO var` yields an array that you can return or iterate. Just ensure to match semantics: Cypher’s `collect` ignores null (since it only collects existing hits). AQL’s collect into naturally just collects what’s iterated (if nothing, you get an empty array, which matches that behavior).

* **Order of execution and using results:** In Cypher, you can refer to a variable after an optional match even if optional yields null. In AQL, you have that variable from the outer scope anyway. Just ensure not to use a field of a null optional variable without a check.

* **Performance pitfalls:**

  * Doing a subquery in a LET for optional is fine, but doing it in a naive way in a hot loop could be costly. The LLM should prefer traversals or direct index lookups where possible. For example, if matching by an indexed property, that’s good. If doing a subquery that scans a whole collection for each outer iteration, that’s potentially slow. In our optional example, we scanned all User for each Device – that’s not ideal. A better approach if possible: if the edge is from device to user (or vice versa), just do one edge lookup (which is indexed) and one document fetch. We did that in the simplified version with `FOR u IN INBOUND d owns` which uses the edge index. So the LLM should try to utilize edge traversals or direct lookups instead of full collection scans.
  * Large traversal depth without filters can be expensive. If Cypher had a broad pattern, maybe Arango might struggle if not using proper indexes or if the graph is large. The LLM might hint at adding appropriate indexes (e.g., on properties used in FILTER or maybe on \_to if doing manual joins, though \_to is covered by edge index by default).
  * If the Cypher query is looking for a specific node by property and then traversing, ensure the property is indexed in Arango for efficiency. Arango supports hash, skiplist, etc., indexes. AQL queries can use those indexes in the FILTER stage.

* **Arango specific:** Remember ArangoDB’s traversal by default does *depth-first*. Cypher’s pattern doesn’t specify search order (Neo4j does some efficient expansions). Usually, it doesn’t matter, but if someone expects a certain order of results, it might differ. Only relevant if the query cares about ordering by path length or such implicitly. If needed, you can specify `OPTIONS { bfs: true }` in AQL to traverse breadth-first (especially if wanting shortest path by unweighted traversal without using the shortest path function, BFS ensures the first time you reach a node is shortest path).

* **No direct equivalent of APOC (Neo4j procedures):** If Cypher query uses special procedures (like `apoc.path.expand` or others), the LLM should try to replicate with AQL logic or note inability. For example, APOC for all simple paths would be complex to do in AQL; probably out of scope unless explicitly needed.

* **Transactions and concurrent writes:** If Cypher assumes an atomic operation (like MERGE within a transaction), Arango’s single query is atomic. But if the translation splits into multiple queries (like separate remove edges then remove node), there’s a slight difference. However, Arango queries can do multiple modifications in one query (that is atomic in single server). Just something to keep in mind.

---

## 12. Optimization Tips for AQL Queries

ArangoDB’s query optimizer and execution model differ from Neo4j’s. Here are tips to ensure the translated queries run efficiently:

* **Use Indexes for Vertex Lookups:** If the Cypher query uses a property to find start nodes (e.g. `MATCH (u:User {email:"x"})`), make sure the corresponding AQL uses an indexed field. In Arango, create a hash index on `User.email` in this case. The LLM’s translation should assume an index is present or advise it. Arango’s explain plan will show if it uses an index for the FILTER. If not, consider adding one. (While the LLM can’t create indexes, it can suggest in documentation that certain fields be indexed for performance.)

* **Edge Index utilization:** ArangoDB automatically indexes `_from` and `_to` on edge collections. Using the traversal (`FOR v IN OUTBOUND/In...`) will automatically use this index to find connected vertices quickly. Even manual filtering like `FOR e IN edges FILTER e._from == someId` will use the edge index on \_from. So leverage that pattern instead of joining on arbitrary fields.

* **Limit scope early:** Use `FILTER` as early as possible in the query to reduce data. AQL tries to push filters down, but writing the query to filter soon (e.g., filter start nodes by property before traversing) is crucial. For instance, don’t traverse entire graph and then filter by property at the end; filter at the vertex selection if possible. Cypher similarly benefits from using selective indexes first.

* **Avoid unnecessary data in traversal:** If you only need certain info, you don’t always have to return full docs. But Arango still has to load the docs to traverse. However, you can tell AQL to **filter during traversal** via `PRUNE` to avoid exploring branches that won’t meet criteria. Example: If you only want devices of a certain type in results and also do not want to traverse beyond a device that is of a wrong type, use `PRUNE` to stop at those. E.g.,

  ```js
  FOR v, e, p IN 1..5 OUTBOUND start DeviceEdges
    PRUNE v.type != "router"   // stop traversing if device is not router
    FILTER v.type == "router"
    RETURN v
  ```

  This prunes branches where the device isn’t a router to avoid deep traversal there. (Caveat: ensure logic fits requirement).

* **Use `OPTIONS { uniqueVertices: "global" }` if needed:** By default, Arango traversal ensures no vertex is visited twice in the *same path*, but it could visit it via a different path. If the graph has cycles and you worry about endless loops or redundant visits, and you want each vertex only once total, you can set `uniqueVertices: "global"`. But this means you won’t get two different paths to the same vertex as separate outputs. Cypher’s default is to allow different paths even if they end at same node. So normally keep default uniqueness (which is "path"). But for certain algorithms, global uniqueness can save work.

* **Projection vs returning whole doc:** If a document has a lot of fields and you only need one or two, it can be slightly more efficient to return an object with just those fields (less network transfer, etc.). Within the query, Arango still had to read the whole doc from disk, but sending less data out is beneficial if result sets are large. The LLM can choose to return just needed fields to keep output concise.

* **Limiting traversal depth:** Always cap the depth with a reasonable maximum as mentioned. If you see Cypher queries that clearly expect a finite result (like “find if there is a connection” might be bounded by some network diameter), choose a safe upper bound. Unlimited can lead to extremely long running queries or errors.

* **Breaking complex queries:** Sometimes a Cypher query does a lot in one go. Arango can also do a lot in one query (and is capable of multi-model joins). But if a single translated query becomes too complex (multiple collects, traversals, subqueries), consider if it’s feasible. The manual can suggest breaking it into smaller queries if needed (but since we are writing an LLM manual, probably we aim to produce one AQL per Cypher if possible).

* **Use `EXPLAIN` and `PROFILE`:** ArangoDB has an `EXPLAIN` feature (via web interface or arangosh) to show the query plan and if indexes are used. If optimizing, one should use it. The LLM cannot do that itself but could recommend the user to do so if performance is an issue.

* **Transaction size (for modifications):** If a Cypher write is creating or updating a huge number of elements, Arango might struggle if the AQL tries to do it in one transaction (which it will, since one AQL = one transaction). The LLM might warn about very large batch operations.

* **Memory considerations:** AQL will build result sets in memory. If a translation involves creating a large intermediate list (like collecting a million elements), it could blow memory. The LLM could hint to avoid collecting too large arrays if not needed, or to stream results if possible (though AQL doesn’t stream out until done by default, except maybe in cursor usage via driver). But in query writing, just be mindful not to do something like `COLLECT ... INTO bigList` and then not use it effectively.

* **Batching optional traversals:** If multiple optional pieces are needed, doing many subqueries could degrade performance. A possible optimization is to get all needed info in one traversal if feasible. For example, instead of doing one optional match for each type of neighbor separately, sometimes one traversal that gathers all could be done and then you filter or pick. This is complex and case-dependent.

In summary, the LLM should focus on producing **correct translations first**, then ensure no obvious performance killers are present:

* Always filter early,
* Use edge index by using OUTBOUND/INBOUND,
* Use appropriate grouping,
* And avoid obviously redundant nested loops.

---

## 13. Examples in a Cybersecurity/Network Context

Finally, let’s solidify understanding with a couple of practical examples using a network security graph scenario:

**Example 1: Find potentially compromised users who logged into a high-risk device.**
Suppose we have `User` nodes, `Device` nodes, and `LOGIN` relationships from User to Device indicating a login event. Devices have a property `riskLevel`. We want users who have logged into any device with `riskLevel = "high"`.

*Cypher:*

```cypher
MATCH (u:User)-[:LOGIN]->(d:Device)
WHERE d.riskLevel = "high"
RETURN DISTINCT u.username;
```

This finds all users who logged into at least one high risk device.

*AQL:*

```js
FOR d IN Device
  FILTER d.riskLevel == "high"
  FOR u IN INBOUND d LOGIN   // users who logged into this device
  RETURN DISTINCT u.username
```

Explanation: We filter devices to only high risk. Then traverse inbound along the LOGIN edges to find users that came into those devices. We use `DISTINCT` to avoid duplicates (since a user might have logged into multiple high-risk devices). ArangoDB doesn’t have `RETURN DISTINCT` as a direct keyword on its own, but you can achieve it by using `COLLECT` without aggregates:

```js
FOR d IN Device
  FILTER d.riskLevel == "high"
  FOR u IN INBOUND d LOGIN
    COLLECT uname = u.username
    RETURN uname
```

This will return each unique username once. Alternatively, `RETURN DISTINCT u.username` is supported in AQL (introduced in some version) as shorthand – if allowed, the LLM can use it; if not, use COLLECT.

**Example 2: Find devices that are not connected to any other device (isolated devices).**
We have `CONNECTED` edges (undirected conceptual connections, stored say one direction only but use ANY for safety).

*Cypher:*

```cypher
MATCH (d:Device)
OPTIONAL MATCH (d)-[:CONNECTED]-(other:Device)
WHERE other IS NULL
RETURN d.name;
```

Cypher here matches each device and then attempts to find a connected neighbor. If none, `other` is null, then it filters to those.

*AQL:*

```js
FOR d IN Device
  LET neighbor = FIRST(FOR x IN ANY d connected RETURN 1)
  FILTER neighbor == null
  RETURN d.name
```

We look for any connected neighbor via an ANY traversal (depth 1). Instead of returning the neighbor, we just return `1` (since we just need existence). If none exist, `FIRST()` gives null. Then we filter those where `neighbor` is null (no connections). We output the device name.

Alternatively, we could do:

```js
FOR d IN Device
  FILTER NOT LENGTH(FOR x IN ANY d connected RETURN 1)
  RETURN d.name
```

Here `LENGTH(...)` returns 0 if no neighbors, and NOT 0 is true, but NOT non-zero is false. However, AQL might require a boolean, so better:

```js
FILTER LENGTH(FOR x IN ANY d connected RETURN 1) == 0
```

works too. The previous approach with LET is clear though.

**Example 3: Shortest path between two users through the network.**
Imagine we want the shortest connection path between two users, where connections can be user->device (USES) and device->device (CONNECTED) and device->user (maybe a user who has an account on device, which is similar to uses). Essentially a path that might go User->Device->User->Device->... until reaching the target user. If we treat this as a multi-graph problem, we might need to traverse two edge collections.

We can define a named graph or just use both edge collections in one query. For simplicity, define that we have `uses` edges (User -> Device) and `connected` edges (Device -> Device). To find a path from one User to another:
*Cypher (conceptual, though Cypher normally deals with one-type relationships unless we do something fancy like an or in pattern):*

```
MATCH (u1:User {name:"Alice"}), (u2:User {name:"Bob"}),
p = shortestPath((u1)-[:USES|CONNECTED*]-(u2))
RETURN p;
```

Cypher can’t directly have two different relationships in one shortestPath unless they were part of the same overall type or one could unify, but let’s assume it could search using either USES or CONNECTED.

*AQL:* We list both edges in ANY SHORTEST\_PATH:

```js
LET start = FIRST(FOR u IN User FILTER u.name == "Alice" RETURN u._id)
LET goal = FIRST(FOR u IN User FILTER u.name == "Bob" RETURN u._id)
FOR v IN ANY SHORTEST_PATH start TO goal uses, connected
  RETURN v.type || ":" || v.name
```

Here, we traverse considering edges from the `uses` collection and `connected` collection. We output each vertex as `"Type:Name"` (assuming each doc has a `type` field like “User” or “Device” and a `name`). The path might look like `["User:Alice", "Device:OfficePC", "Device:Server1", "User:Bob"]` if Alice uses OfficePC, that is connected to Server1 which Bob uses.

This showcases multi-collection traversal in shortest path. We could also have defined a graph including both edges and done `GRAPH "NetworkGraph"` if configured.

**Example 4: Update example – Mark all devices older than 5 years as deprecated.**
Cypher:

```cypher
MATCH (d:Device)
WHERE d.age > 5
SET d.deprecated = true;
```

AQL:

```js
FOR d IN Device
  FILTER d.age > 5
  UPDATE d WITH { deprecated: true } IN Device
```

This goes through devices older than 5 and updates a field. If we wanted to return how many were updated, we could do `COLLECT WITH COUNT INTO count RETURN count` or use `RETURN NEW` in the UPDATE to see the new docs (but that would list all docs, not just count).

**Example 5: Delete example – Remove a user and their relations.**
Cypher:

```cypher
MATCH (u:User {name:"Eve"})
DETACH DELETE u;
```

AQL:

```js
FOR u IN User
  FILTER u.name == "Eve"
  FOR rel IN uses
    FILTER rel._from == u._id
    REMOVE rel IN uses
  REMOVE u IN User
```

This removes edges where the user was the source (e.g., they used devices). If the user had incoming edges (maybe from other relationships like FRIEND with another user?), those would need removal too. This is a bit manual as noted. If many types of edges connect to User, you’d have to remove in each relevant edge collection. In a known graph scenario, one might call a server-side function or multiple queries.

**Closing Best Practices on Data Model:**

* Representing relationships in Arango requires careful choice of edge collections. Too many edge collections for every type can be fine, but if there are a lot of types, consider using a single edge collection with a `type` attribute and then filtering by that. That approach could simplify some traversals (just one edge col), but filtering by type is a runtime check. Using multiple collections (one per type) can be faster and mirrors Cypher semantics well (each rel type separate). The translation should assume the straightforward mapping (each rel type -> one edge collection) unless told otherwise.

* Multi-label nodes can be modeled by either duplication in multiple collections or having an array field. Usually, one would just use a field for roles or tags instead of multiple labels in Arango.

* When designing queries, try to minimize the scope of data scanned. Use specific starting points whenever possible (e.g., an initial MATCH by key in Cypher -> a direct document lookup in Arango by \_key using `DOCUMENT("Collection/key")` function). If the Cypher uses an indexed lookup, replicate with an indexed lookup.

---

## 14. Conclusion

Translating Cypher to AQL involves mapping the pattern-based paradigm of Cypher to the loop/filter paradigm of AQL. Keep in mind the structural differences: ArangoDB requires explicit handling of directions, does not support implicit optional matches or unlimited traversals without bounds, and needs explicit grouping for aggregates. However, AQL is very powerful and can accomplish the same tasks, often with similar or better performance if used correctly (thanks to indexes and its ability to handle mixed workloads).

By following the guidelines in this manual:

* **Identify key clauses** in the Cypher query and replace them with their AQL equivalents (MATCH -> FOR, WHERE -> FILTER, etc.).
* **Use Arango’s traversal constructs** to navigate graphs, respecting directionality and depth.
* **Replicate any filtering and post-processing** (aggregations, sorting, limits) with AQL’s constructs, being mindful of necessary COLLECT or subqueries.
* **Double-check logic for optional parts** to ensure no results are lost.
* **Optimize** by filtering early and leveraging indexes and the edge index for graph walks.
* **Test the query** on expected inputs to ensure the results align with the Cypher version, adjusting if necessary for off-by-one in depth or null-handling differences.

Following these steps will allow the LLM to produce correct and efficient AQL queries for virtually any Cypher query it encounters, enabling seamless interoperability between Neo4j-style graph queries and ArangoDB’s multi-model query language.

**References:**

* ArangoDB Documentation – Graph Traversals and AQL syntax
* ArangoDB Official Blog – *Comparing ArangoDB AQL to Neo4j Cypher*
* Stack Overflow – Optional match in ArangoDB AQL using subqueries
* ArangoDB AQL Functions – string, list, and object handling
