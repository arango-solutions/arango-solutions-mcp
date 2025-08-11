from typing import Any, Dict, List, Optional

from pydantic import Field

from agents.graph_management_agent import GraphManagementAgent
from server import mcp_app

graph_agent = GraphManagementAgent()


@mcp_app.tool(
    name="list-graphs",
    description="""Lists all named graphs configured for relationship modeling and traversal.
    
    Named graphs in ArangoDB provide:
    - Structured relationship definitions between collections
    - Optimized graph traversal operations
    - Enforced data consistency for graph structures
    - Simplified graph query syntax
    - Performance benefits for complex relationship queries
    
    Graph components:
    - Vertex collections: Store entities (users, products, locations)
    - Edge collections: Store relationships (follows, purchases, located_in)
    - Edge definitions: Define allowed connections between vertex types
    
    Common graph patterns:
    - Social networks (users connected by friendships)
    - E-commerce (customers, products, orders, reviews)
    - Knowledge graphs (concepts and their relationships)
    - Organizational charts (employees and reporting structures)
    - Transportation networks (locations connected by routes)
    
    Use this to explore available graph structures and relationship models.
    """,
)
async def list_graphs(
    database_name: Optional[str] = Field(
        default=None,
        description="""Target database name. Uses default database if not specified.
        
        Examples:
        - 'social_network' - database with user relationships
        - 'ecommerce' - product and customer relationship data
        - 'knowledge_base' - conceptual relationship graphs
        
        Graphs are database-specific configurations.
        """,
    )
) -> Dict[str, Any]:
    return await graph_agent.arun({"operation": "list_graphs", "database_name": database_name})


@mcp_app.tool(
    name="create-graph",
    description="""Creates a named graph structure for modeling complex relationships.
    
    Named graphs provide:
    - Structured relationship definitions between entity types
    - Optimized graph traversal performance
    - Data consistency and validation
    - Simplified graph query operations
    - Clear data model documentation
    
    Graph design patterns:
    
    Social Network:
    - Vertices: users, groups, pages
    - Edges: follows, likes, member_of
    
    E-commerce:
    - Vertices: customers, products, categories, orders
    - Edges: purchases, belongs_to, contains, reviews
    
    Knowledge Graph:
    - Vertices: concepts, entities, documents
    - Edges: relates_to, instance_of, mentions
    
    Best practices:
    - Plan your graph schema before creation
    - Use descriptive names for collections and relationships
    - Consider query patterns when designing edge definitions
    - Start simple and evolve the graph structure
    """,
)
async def create_graph(
    graph_name: str = Field(
        description="""Unique name for the new graph structure.
        
        Examples:
        - 'social_network' - for user relationships and interactions
        - 'product_catalog' - for product hierarchies and recommendations
        - 'knowledge_graph' - for conceptual relationships
        - 'org_chart' - for organizational hierarchy
        
        Naming conventions:
        - Use descriptive names indicating the domain
        - Reflect the business purpose or use case
        - Avoid conflicts with collection names
        """
    ),
    edge_definitions: List[Dict[str, Any]] = Field(
        description="""List of relationship definitions between vertex collections.
        
        Each edge definition specifies:
        - edge_collection: Name of collection storing relationships
        - from_vertex_collections: Source entity types
        - to_vertex_collections: Target entity types
        
        Examples:
        
        Social network:
        [{
          "edge_collection": "follows",
          "from_vertex_collections": ["users"],
          "to_vertex_collections": ["users"]
        }, {
          "edge_collection": "likes",
          "from_vertex_collections": ["users"],
          "to_vertex_collections": ["posts", "comments"]
        }]
        
        E-commerce:
        [{
          "edge_collection": "purchases",
          "from_vertex_collections": ["customers"],
          "to_vertex_collections": ["products"]
        }, {
          "edge_collection": "belongs_to",
          "from_vertex_collections": ["products"],
          "to_vertex_collections": ["categories"]
        }]
        
        Edge collections will be created as 'edge' type automatically.
        """
    ),
    orphan_collections: Optional[List[str]] = Field(
        default=None,
        description="""Additional vertex collections included in the graph but not connected by edges.
        
        Examples:
        - ['archived_users'] - users without current relationships
        - ['product_templates'] - products not yet in catalog
        - ['draft_content'] - content not yet published
        
        Orphan collections can be connected later by adding edge definitions.
        Optional - most graphs don't need orphan collections initially.
        """,
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await graph_agent.arun(
        {
            "operation": "create_graph",
            "database_name": database_name,
            "graph_name": graph_name,
            "edge_definitions": edge_definitions,
            "orphan_collections": orphan_collections,
        }
    )


@mcp_app.tool(
    name="delete-graph",
    description="""Removes a named graph definition and optionally its collections.
    
    Graph deletion options:
    - Delete graph definition only (default): Preserves all data, removes graph structure
    - Delete graph and collections: Removes graph definition AND all associated data
    
    ⚠️  WARNING: If drop_collections=true:
    - ALL vertex and edge data will be permanently deleted
    - Applications using these collections will break
    - Graph traversal queries will fail
    - Cannot be undone
    
    Safe deletion (drop_collections=false):
    - Removes only the graph definition
    - Preserves all collection data
    - Collections can be used independently
    - Graph can be recreated with same collections
    
    Use cases:
    - Restructuring graph definitions
    - Removing obsolete graph models
    - Database cleanup and optimization
    - Migrating to new graph structures
    """,
)
async def delete_graph(
    graph_name: str = Field(
        description="""Name of the graph to delete.
        
        Examples:
        - 'old_social_network' - obsolete social graph
        - 'test_graph' - temporary test graph
        - 'deprecated_relationships' - replaced graph structure
        """
    ),
    drop_collections: bool = Field(
        default=False,
        description="""⚠️  DANGER: Whether to also delete all collections and data.
        
        - false (default): Delete only graph definition, preserve data
        - true: Delete graph definition AND all vertex/edge collections
        
        ONLY set to true if you want to permanently delete all graph data.
        This includes all vertices, edges, and relationships - cannot be undone.
        
        Recommended: Use false to preserve data unless doing complete cleanup.
        """,
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await graph_agent.arun(
        {
            "operation": "delete_graph",
            "database_name": database_name,
            "graph_name": graph_name,
            "drop_collections": drop_collections,
        }
    )


@mcp_app.tool(
    name="create-edge",
    description="""Creates a relationship (edge) between two entities in a graph.
    
    Edges represent relationships and connections:
    - Social: user follows another user
    - E-commerce: customer purchases product
    - Organizational: employee reports to manager
    - Knowledge: concept relates to another concept
    
    Edge properties can include:
    - Relationship metadata (strength, weight, type)
    - Temporal information (created_at, valid_from/to)
    - Contextual data (reason, source, confidence)
    - Business attributes (amount, quantity, status)
    
    Common relationship patterns:
    - Friendships: mutual with strength scores
    - Purchases: with amount, date, payment method
    - Hierarchies: with roles and permissions
    - Recommendations: with relevance scores
    
    Best practices:
    - Include meaningful edge attributes
    - Use consistent data patterns
    - Consider bidirectional vs unidirectional relationships
    - Add timestamps for temporal analysis
    """,
)
async def create_edge(
    graph_name: str = Field(
        description="""Name of the graph containing the edge collection.
        
        Examples:
        - 'social_network' - for user relationship graphs
        - 'product_catalog' - for product recommendation graphs
        - 'knowledge_graph' - for conceptual relationship graphs
        
        The graph must already exist and define this edge collection.
        """
    ),
    edge_collection_name: str = Field(
        description="""Name of the edge collection where the relationship will be stored.
        
        Examples:
        - 'follows' - user following relationships
        - 'purchases' - customer purchase relationships
        - 'reports_to' - organizational hierarchy
        - 'similar_to' - product similarity relationships
        
        Must be defined in the graph's edge definitions.
        """
    ),
    from_vertex_id: str = Field(
        description="""Full document ID of the source vertex (format: 'collection/key').
        
        Examples:
        - 'users/alice' - user Alice as source
        - 'customers/cust_123' - customer as source
        - 'products/prod_456' - product as source
        - 'employees/emp_789' - employee as source
        
        Must be a valid document ID from an allowed 'from' collection.
        Use format 'collection_name/document_key'.
        """
    ),
    to_vertex_id: str = Field(
        description="""Full document ID of the target vertex (format: 'collection/key').
        
        Examples:
        - 'users/bob' - user Bob as target
        - 'products/laptop_pro' - product as target
        - 'categories/electronics' - category as target
        - 'managers/mgr_456' - manager as target
        
        Must be a valid document ID from an allowed 'to' collection.
        Use format 'collection_name/document_key'.
        """
    ),
    edge_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""Additional attributes and metadata for the relationship.
        
        Examples:
        
        Social relationship:
        {
          "relationship_type": "friend",
          "since": "2023-01-15",
          "strength": 0.8,
          "mutual": true
        }
        
        Purchase relationship:
        {
          "amount": 299.99,
          "currency": "USD",
          "purchase_date": "2023-12-01",
          "payment_method": "credit_card",
          "quantity": 2
        }
        
        Organizational relationship:
        {
          "role": "direct_report",
          "start_date": "2023-06-01",
          "department": "engineering",
          "level": 1
        }
        
        Leave empty for simple relationships without additional data.
        """,
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await graph_agent.arun(
        {
            "operation": "create_edge",
            "database_name": database_name,
            "graph_name": graph_name,
            "edge_collection_name": edge_collection_name,
            "from_vertex_id": from_vertex_id,
            "to_vertex_id": to_vertex_id,
            "edge_data": edge_data,
        }
    )
