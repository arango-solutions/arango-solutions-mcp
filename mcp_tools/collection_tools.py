from typing import Any, Dict, List, Optional, Union

from pydantic import Field

from agents.collection_management_agent import CollectionManagementAgent
from server import mcp_app

collection_agent = CollectionManagementAgent()


@mcp_app.tool(
    name="list-collections",
    description="""Lists all user-defined collections in an ArangoDB database.
    
    Collections in ArangoDB are containers for documents, similar to tables in SQL.
    This tool shows collections you've created, excluding system collections (starting with '_').
    
    Collection types:
    - Document collections: Store JSON documents (like users, products, orders)
    - Edge collections: Store relationships between documents (for graphs)
    
    Use this to:
    - Explore database structure and available data
    - Understand your data model
    - Check collection names before operations
    - Audit database contents
    
    Returned information includes:
    - Collection name and type
    - Document count and status
    - Collection metadata
    """,
)
async def list_collections(
    database_name: Optional[str] = Field(
        default=None,
        description="""Target database name to list collections from.
        
        Examples:
        - 'production' - main application database
        - 'analytics' - analytics and reporting data
        - 'staging' - staging environment
        
        If not specified, uses the server's default database.
        Use 'list-databases' tool to see available databases.
        """,
    ),
) -> Dict[str, Any]:
    return await collection_agent.arun(
        {"operation": "list_collections", "database_name": database_name}
    )


@mcp_app.tool(
    name="create-collection",
    description="""Creates a new collection for storing documents or relationships.

    Collection types:
    - Document collections: Store business entities (users, products, orders)
    - Edge collections: Store relationships between documents (follows, purchases)

    Cluster / sharding options (ignored on single-server deployments):
    - number_of_shards: How many shards to split the data across
    - shard_keys: Which document fields determine shard placement
    - replication_factor: How many copies of each shard (or 'satellite')
    - write_concern: Minimum replicas that must confirm a write
    - sharding_strategy: Algorithm for mapping documents to shards

    Computed values (3.10+):
    - Automatically compute and store derived fields on write

    Best practices:
    - Use descriptive names (users, products, follows, purchases)
    - Choose shard keys that distribute data evenly and match query patterns
    - Set replication_factor >= 2 in production clusters
    """,
)
async def create_collection(
    collection_name: str = Field(
        description="""Name for the new collection.

        Naming conventions:
        - Use lowercase, plural nouns for document collections
        - Use verb forms for edge collections (follows, likes, contains)
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
    collection_type: str = Field(
        default="document",
        description="""Type of collection: 'document' (default) or 'edge'.
        Choose 'edge' for graph relationships requiring _from and _to fields.
        """,
    ),
    number_of_shards: Optional[int] = Field(
        default=None,
        description="""Number of shards for the collection (cluster only).
        More shards = better write parallelism but more overhead.
        Typical values: 1 (small), 3-6 (medium), 9+ (large/high-throughput).
        Ignored on single-server deployments.
        """,
    ),
    shard_keys: Optional[List[str]] = Field(
        default=None,
        description="""Document fields used to determine shard placement (cluster only).
        Defaults to ['_key'] if not specified.

        Examples:
        - ['_key'] — default, uniform distribution
        - ['region'] — co-locate documents by region
        - ['tenant_id'] — multi-tenant isolation
        - ['customer_id', 'order_date'] — compound key

        Choose keys that appear in most queries to enable shard pruning.
        Cannot be changed after collection creation.
        """,
    ),
    replication_factor: Optional[Union[int, str]] = Field(
        default=None,
        description="""Number of shard replicas (cluster only).
        - 1: no replication (not recommended for production)
        - 2: one primary + one follower (default in most clusters)
        - 3+: higher durability
        - 'satellite': replicate to ALL DB servers (Enterprise only,
          useful for small lookup tables to avoid network joins)
        """,
    ),
    write_concern: Optional[int] = Field(
        default=None,
        description="""Minimum number of replicas that must confirm a write (cluster only).
        Must be <= replication_factor. Higher values = stronger durability
        guarantees but higher write latency. Default is 1.
        """,
    ),
    sharding_strategy: Optional[str] = Field(
        default=None,
        description="""Sharding algorithm (cluster only). Options:
        - 'community-compat': default community sharding
        - 'enterprise-compat': default enterprise sharding
        - 'enterprise-smart-edge-compat': for SmartGraph edge collections
        - 'hash': hash-based distribution
        - 'enterprise-hash-smart-edge': SmartGraph hash distribution
        Usually left as default unless building SmartGraphs.
        """,
    ),
    computed_values: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="""Computed values to auto-generate fields on write (ArangoDB 3.10+).

        Each entry: {
          "name": "field_name",
          "expression": "RETURN ..AQL expression..",
          "overwrite": true/false,
          "computeOn": ["insert", "update", "replace"],
          "keepNull": false,
          "failOnWarning": false
        }

        Example — auto-set updatedAt timestamp:
        [{"name": "updatedAt", "expression": "RETURN DATE_ISO8601(DATE_NOW())",
          "overwrite": true, "computeOn": ["insert", "update", "replace"]}]
        """,
    ),
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "operation": "create_collection",
        "database_name": database_name,
        "collection_name": collection_name,
        "collection_type": collection_type,
    }
    if number_of_shards is not None:
        payload["number_of_shards"] = number_of_shards
    if shard_keys is not None:
        payload["shard_keys"] = shard_keys
    if replication_factor is not None:
        payload["replication_factor"] = replication_factor
    if write_concern is not None:
        payload["write_concern"] = write_concern
    if sharding_strategy is not None:
        payload["sharding_strategy"] = sharding_strategy
    if computed_values is not None:
        payload["computed_values"] = computed_values
    return await collection_agent.arun(payload)


@mcp_app.tool(
    name="delete-collection",
    description="""Permanently deletes a collection and all its documents.
    
     WARNING: This operation is irreversible and will:
    - Delete ALL documents in the collection
    - Remove all indexes associated with the collection
    - Break any graph definitions using this collection
    - Cannot be undone
    
    Use with extreme caution in production environments.
    
    Consider alternatives:
    - Backup the collection before deletion
    - Use document filtering instead of collection deletion
    - Archive data to another collection first
    - Use database branching for testing destructive operations
    
    Common use cases:
    - Cleaning up temporary collections
    - Removing test data
    - Database schema changes
    - Development environment cleanup
    """,
)
async def delete_collection(
    collection_name: str = Field(
        description="""Name of the collection to permanently delete.
        
         DANGER: All data in this collection will be lost forever.
        
        Examples:
        - 'test_users' - temporary test collection
        - 'old_products' - deprecated product data
        - 'temp_import' - temporary import collection
        
        Double-check the name before execution. This cannot be undone.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await collection_agent.arun(
        {
            "operation": "delete_collection",
            "database_name": database_name,
            "collection_name": collection_name,
        }
    )


@mcp_app.tool(
    name="get-collection-properties",
    description="""Retrieves detailed information about a collection's configuration and statistics.
    
    Provides comprehensive collection metadata including:
    - Document count and storage statistics
    - Collection type and configuration
    - Index information and performance data
    - Revision tracking and sync details
    - Sharding and distribution info (in cluster setups)
    
    Use this to:
    - Monitor collection size and growth
    - Understand collection configuration
    - Plan capacity and performance optimization
    - Debug collection-related issues
    - Audit database structure
    
    Particularly useful for:
    - Performance analysis and optimization
    - Storage planning and monitoring
    - Understanding data distribution
    - Collection health checks
    """,
)
async def get_collection_properties(
    collection_name: str = Field(
        description="""Name of the collection to analyze.
        
        Examples:
        - 'users' - get user collection stats
        - 'products' - analyze product catalog size
        - 'orders' - check order collection growth
        
        Returns detailed statistics about document count, storage size,
        indexes, and performance characteristics.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await collection_agent.arun(
        {
            "operation": "get_collection_properties",
            "database_name": database_name,
            "collection_name": collection_name,
        }
    )
