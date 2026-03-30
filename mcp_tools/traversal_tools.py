from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from agents.graph_traversal_agent import GraphTraversalAgent
from server import mcp_app

traversal_agent = GraphTraversalAgent()


@mcp_app.tool(
    name="graph-traverse",
    description="""Traverses a graph from a starting vertex, following edges to discover
    connected vertices at a given depth range.

    This is the fundamental graph exploration operation. Use it to:
    - Explore relationships from a starting point
    - Find all entities within N hops (friends-of-friends, supply chains)
    - Discover reachable vertices with optional vertex/edge filters
    - Analyze subgraphs around a specific entity

    Directions:
    - OUTBOUND: follow edges away from start (e.g., "who does Alice follow?")
    - INBOUND: follow edges toward start (e.g., "who follows Alice?")
    - ANY: follow edges in both directions

    Can traverse a named graph or raw edge collection(s).
    Returns vertices, edges, and optionally full paths.
    """,
)
async def graph_traverse(
    start_vertex: str = Field(
        description="""Starting vertex ID (format: 'collection/key').

        Examples:
        - 'users/alice'
        - 'products/laptop_pro'
        - 'airports/JFK'
        """
    ),
    graph_name: Optional[str] = Field(
        default=None,
        description="Named graph to traverse. Provide this OR edge_collections.",
    ),
    edge_collections: Optional[List[str]] = Field(
        default=None,
        description="Edge collection(s) to traverse. Alternative to graph_name.",
    ),
    direction: Literal["OUTBOUND", "INBOUND", "ANY"] = Field(
        default="OUTBOUND",
        description="Traversal direction: 'OUTBOUND', 'INBOUND', or 'ANY'.",
    ),
    min_depth: int = Field(
        default=1,
        description="Minimum traversal depth (default 1).",
    ),
    max_depth: int = Field(
        default=1,
        description="Maximum traversal depth. Set to 2+ for multi-hop traversals.",
    ),
    limit: int = Field(
        default=100,
        description="Maximum number of results to return.",
    ),
    vertex_filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""Filter visited vertices by attribute values (equality).

        Example: {'status': 'active', 'country': 'US'}
        """,
    ),
    edge_filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""Filter traversed edges by attribute values (equality).

        Example: {'type': 'friend', 'weight': 1.0}
        """,
    ),
    return_vertices: bool = Field(default=True, description="Include vertices in results."),
    return_edges: bool = Field(default=True, description="Include edges in results."),
    return_paths: bool = Field(default=False, description="Include full paths in results."),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await traversal_agent.arun(
        {
            "operation": "traverse",
            "database_name": database_name,
            "start_vertex": start_vertex,
            "graph_name": graph_name,
            "edge_collections": edge_collections,
            "direction": direction,
            "min_depth": min_depth,
            "max_depth": max_depth,
            "limit": limit,
            "vertex_filters": vertex_filters,
            "edge_filters": edge_filters,
            "return_vertices": return_vertices,
            "return_edges": return_edges,
            "return_paths": return_paths,
        }
    )


@mcp_app.tool(
    name="graph-shortest-path",
    description="""Finds the shortest path between two vertices in a graph.

    Uses ArangoDB's SHORTEST_PATH algorithm which is optimized for
    finding a single shortest path efficiently.

    Use cases:
    - Degrees of separation between two users
    - Shortest route between locations
    - Closest supply chain connection
    - Minimum hops between any two entities

    Supports weighted paths via weight_attribute for finding the
    lowest-cost path rather than the fewest-hop path.

    Returns the sequence of vertices and edges forming the path.
    """,
)
async def graph_shortest_path(
    start_vertex: str = Field(description="Starting vertex ID (format: 'collection/key')."),
    target_vertex: str = Field(description="Target vertex ID (format: 'collection/key')."),
    graph_name: Optional[str] = Field(
        default=None,
        description="Named graph. Provide this OR edge_collections.",
    ),
    edge_collections: Optional[List[str]] = Field(
        default=None,
        description="Edge collection(s). Alternative to graph_name.",
    ),
    direction: Literal["OUTBOUND", "INBOUND", "ANY"] = Field(
        default="OUTBOUND",
        description="Edge direction: 'OUTBOUND', 'INBOUND', or 'ANY'.",
    ),
    weight_attribute: Optional[str] = Field(
        default=None,
        description="""Edge attribute for weighted shortest path.
        If set, finds the lowest-weight path instead of fewest hops.

        Example: 'distance', 'cost', 'duration'
        """,
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await traversal_agent.arun(
        {
            "operation": "shortest_path",
            "database_name": database_name,
            "start_vertex": start_vertex,
            "target_vertex": target_vertex,
            "graph_name": graph_name,
            "edge_collections": edge_collections,
            "direction": direction,
            "weight_attribute": weight_attribute,
        }
    )


@mcp_app.tool(
    name="graph-k-shortest-paths",
    description="""Finds multiple shortest paths between two vertices in a graph.

    Returns up to K alternative shortest paths, ranked by length (or weight).
    Useful when you need:
    - Alternative routes (e.g., backup paths in a network)
    - Multiple connection patterns between entities
    - Redundancy analysis (how many ways can A reach B?)
    - Ranked path options with different characteristics

    Each result includes the full path with vertices and edges.
    """,
)
async def graph_k_shortest_paths(
    start_vertex: str = Field(description="Starting vertex ID (format: 'collection/key')."),
    target_vertex: str = Field(description="Target vertex ID (format: 'collection/key')."),
    graph_name: Optional[str] = Field(
        default=None,
        description="Named graph. Provide this OR edge_collections.",
    ),
    edge_collections: Optional[List[str]] = Field(
        default=None,
        description="Edge collection(s). Alternative to graph_name.",
    ),
    direction: Literal["OUTBOUND", "INBOUND", "ANY"] = Field(
        default="OUTBOUND",
        description="Edge direction: 'OUTBOUND', 'INBOUND', or 'ANY'.",
    ),
    limit: int = Field(
        default=5,
        description="Maximum number of paths to return (K).",
    ),
    weight_attribute: Optional[str] = Field(
        default=None,
        description="Edge attribute for weighted path calculation.",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await traversal_agent.arun(
        {
            "operation": "k_shortest_paths",
            "database_name": database_name,
            "start_vertex": start_vertex,
            "target_vertex": target_vertex,
            "graph_name": graph_name,
            "edge_collections": edge_collections,
            "direction": direction,
            "limit": limit,
            "weight_attribute": weight_attribute,
        }
    )


@mcp_app.tool(
    name="graph-neighbors",
    description="""Finds all neighbor vertices connected to a starting vertex.

    A simplified traversal that returns distinct connected vertices at
    a specific depth. This is the "who is connected to X?" query.

    Use cases:
    - Direct friends/connections of a user
    - Products in the same category
    - Immediate dependencies of a component
    - Adjacent nodes in any network

    Results are deduplicated by default so each neighbor appears once.
    """,
)
async def graph_neighbors(
    start_vertex: str = Field(description="Starting vertex ID (format: 'collection/key')."),
    graph_name: Optional[str] = Field(
        default=None,
        description="Named graph. Provide this OR edge_collections.",
    ),
    edge_collections: Optional[List[str]] = Field(
        default=None,
        description="Edge collection(s). Alternative to graph_name.",
    ),
    direction: Literal["OUTBOUND", "INBOUND", "ANY"] = Field(
        default="ANY",
        description="Edge direction: 'OUTBOUND', 'INBOUND', or 'ANY' (default: ANY).",
    ),
    depth: int = Field(
        default=1,
        description="How many hops away to look (default: 1 = direct neighbors).",
    ),
    limit: int = Field(
        default=100,
        description="Maximum number of neighbors to return.",
    ),
    vertex_filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filter neighbors by attribute values (equality).",
    ),
    deduplicate: bool = Field(
        default=True,
        description="Return each neighbor only once (default: true).",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Target database. Uses default if not specified.",
    ),
) -> Dict[str, Any]:
    return await traversal_agent.arun(
        {
            "operation": "neighbors",
            "database_name": database_name,
            "start_vertex": start_vertex,
            "graph_name": graph_name,
            "edge_collections": edge_collections,
            "direction": direction,
            "depth": depth,
            "limit": limit,
            "vertex_filters": vertex_filters,
            "deduplicate": deduplicate,
        }
    )
