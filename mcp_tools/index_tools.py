from typing import Any, Dict, Optional

from pydantic import Field

from agents.index_management_agent import IndexManagementAgent
from server import mcp_app

index_agent = IndexManagementAgent()


@mcp_app.tool(
    name="list-indexes",
    description="""Lists all indexes for a collection to understand query performance optimization.
    
    Indexes in ArangoDB accelerate query performance by:
    - Creating fast lookup structures for frequently queried fields
    - Enabling efficient sorting and filtering operations
    - Supporting unique constraints and data validation
    - Optimizing graph traversal and join operations
    
    Index types shown:
    - Primary: Automatically created unique index on _key field
    - Persistent: General-purpose B-tree indexes for most queries
    - TTL: Time-to-live indexes for automatic document expiration
    - Inverted: Full-text search indexes for text content
    - Geo: Geospatial indexes for location-based queries
    - Multi-dimensional: Indexes for complex data structures
    
    Use this to:
    - Analyze query performance bottlenecks
    - Plan index optimization strategies
    - Understand existing performance optimizations
    - Monitor index usage and effectiveness
    - Debug slow query performance
    """,
)
async def list_indexes(
    collection_name: str = Field(
        description="""Name of the collection to analyze indexes for.
        
        Examples:
        - 'users' - analyze user collection indexes
        - 'products' - check product catalog performance
        - 'orders' - review order query optimization
        - 'events' - examine event logging indexes
        
        Returns all indexes including:
        - Primary index (always present)
        - Custom indexes for performance
        - Index statistics and usage data
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await index_agent.arun(
        {
            "operation": "list_indexes",
            "database_name": database_name,
            "collection_name": collection_name,
        }
    )


@mcp_app.tool(
    name="create-index",
    description="""Creates a new index to optimize query performance for specific access patterns.

    Index types and use cases:

    Persistent indexes (most common):
    - Single field: Fast lookups on one field
    - Multi-field: Compound queries and sorting
    - Unique: Enforce data uniqueness constraints
    - Sparse: Skip null values to save space

    Specialized indexes:
    - TTL: Automatic document expiration
    - Inverted: Full-text search capabilities
    - Geo: Location-based queries
    - Multi-dimensional (mdi): Complex data structures

    Vector indexes (3.12.4+, requires --vector-index startup option):
    - ANN (Approximate Nearest Neighbor) search using FAISS
    - Metrics: cosine, l2 (Euclidean), innerProduct (3.12.6+)
    - Documents MUST have vector data before index creation
    - Use with APPROX_NEAR_COSINE/L2/INNER_PRODUCT AQL functions
    - Or use the dedicated 'vector-search' tool for convenience

    Best practices:
    - Analyze query patterns before creating indexes
    - For vector indexes, populate data BEFORE creating the index
    - Use compound indexes for multi-field queries
    - Monitor index usage and remove unused indexes
    """,
)
async def create_index(
    collection_name: str = Field(
        description="""Name of the collection to add the index to.
        
        Examples:
        - 'users' - for user lookup optimization
        - 'products' - for product search performance
        - 'orders' - for order status and date queries
        - 'events' - for time-based event queries
        """
    ),
    index_definition: Dict[str, Any] = Field(
        description="""Index configuration specifying type, fields, and options.

        Common index definitions:

        Single field index:
        {"type": "persistent", "fields": ["email"], "unique": true,
         "name": "unique_email_idx"}

        Multi-field compound index:
        {"type": "persistent", "fields": ["category", "price", "created_at"],
         "name": "product_search_idx"}

        Full-text search index:
        {"type": "inverted",
         "fields": [{"name": "title", "analyzer": "text_en"},
                    {"name": "description", "analyzer": "text_en"}],
         "name": "content_search_idx"}

        TTL index for automatic cleanup:
        {"type": "ttl", "fields": ["expires_at"], "expireAfterSeconds": 0,
         "name": "auto_expire_idx"}

        Geospatial index:
        {"type": "geo", "fields": ["location"], "geoJson": true,
         "name": "location_idx"}

        Vector (ANN) index (3.12.4+):
        {"type": "vector", "fields": ["embedding"],
         "params": {"metric": "cosine", "dimension": 768, "nLists": 100},
         "name": "embedding_cosine_idx"}

        Vector index params:
        - metric: "cosine" | "l2" | "innerProduct"
        - dimension: number of elements in the embedding array
        - nLists: Voronoi cells (~15 * sqrt(N) recommended)
        - defaultNProbe: centroids to search (default 1, higher = better recall)
        - trainingIterations: (default 25)

        Required fields:
        - type: persistent, inverted, ttl, geo, vector, mdi, mdi-prefixed
        - fields: Array of field names to index
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await index_agent.arun(
        {
            "operation": "create_index",
            "database_name": database_name,
            "collection_name": collection_name,
            "index_definition": index_definition,
        }
    )


@mcp_app.tool(
    name="delete-index",
    description="""Removes an index to free up storage space and improve write performance.
    
     WARNING: Deleting an index will:
    - Slow down queries that depend on this index
    - May cause query timeouts for large collections
    - Cannot be easily undone (requires recreation and rebuild time)
    - Improve write performance by reducing index maintenance overhead
    
    Before deletion:
    - Analyze query patterns to ensure index isn't needed
    - Monitor query performance after removal
    - Consider the impact on application response times
    - Have a rollback plan to recreate if needed
    
    Protected indexes:
    - Primary index (_key) cannot be deleted
    - System indexes are protected
    
    Use cases:
    - Removing unused or redundant indexes
    - Optimizing write performance
    - Database maintenance and cleanup
    - Index strategy optimization
    
    Best practices:
    - Test performance impact in staging first
    - Remove indexes during low-traffic periods
    - Monitor query performance after deletion
    """,
)
async def delete_index(
    collection_name: str = Field(
        description="""Name of the collection containing the index to delete.
        
        Examples:
        - 'users' - remove unused user indexes
        - 'products' - optimize product collection performance
        - 'events' - clean up event logging indexes
        """
    ),
    index_id_or_name: str = Field(
        description="""Index identifier - either the auto-generated ID or custom name.
        
        Examples:
        - Index ID: '2001234' (auto-generated numeric ID)
        - Index name: 'email_unique_idx' (custom name from creation)
        - Index name: 'product_search_idx' (compound index name)
        
         CAUTION: Cannot delete the primary index (_key field).
        
        Use 'list-indexes' to see available indexes and their IDs/names.
        Prefer using custom names for better maintainability.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await index_agent.arun(
        {
            "operation": "delete_index",
            "database_name": database_name,
            "collection_name": collection_name,
            "index_id_or_name": index_id_or_name,
        }
    )
