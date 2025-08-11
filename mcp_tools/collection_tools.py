from typing import Any, Dict, Optional  # List removed as it's not directly used for type hints here

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
    )
) -> Dict[str, Any]:
    return await collection_agent.arun(
        {"operation": "list_collections", "database_name": database_name}
    )


@mcp_app.tool(
    name="create-collection",
    description="""Creates a new collection for storing documents or relationships.
    
    Collection types:
    - Document collections: Store business entities (users, products, orders, etc.)
    - Edge collections: Store relationships between documents (follows, purchases, contains)
    
    Document collections are used for:
    - User profiles and accounts
    - Product catalogs
    - Orders and transactions
    - Content and media
    - Configuration data
    
    Edge collections enable graph functionality:
    - Social networks (user follows user)
    - E-commerce (user purchases product)
    - Organizational charts (employee reports to manager)
    - Knowledge graphs (concept relates to concept)
    
    Best practices:
    - Use descriptive names (users, products, follows, purchases)
    - Plan your data model before creating collections
    - Consider indexing needs for frequently queried fields
    """,
)
async def create_collection(
    collection_name: str = Field(
        description="""Name for the new collection. Should be descriptive and follow naming conventions.
        
        Good examples:
        - 'users' - for user accounts and profiles
        - 'products' - for product catalog
        - 'orders' - for e-commerce orders
        - 'follows' - for social following relationships (edge)
        - 'purchases' - for purchase relationships (edge)
        
        Naming conventions:
        - Use lowercase, plural nouns for document collections
        - Use verb forms for edge collections (follows, likes, contains)
        - Avoid spaces and special characters
        - Be consistent across your application
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
    collection_type: str = Field(
        default="document",
        description="""Type of collection to create.
        
        Options:
        - 'document' (default): For storing business entities and data objects
        - 'edge': For storing relationships between documents (required for graphs)
        
        Choose 'edge' when:
        - Modeling relationships (friendships, purchases, hierarchies)
        - Building graph structures
        - Need to traverse connections between entities
        
        Edge collections require _from and _to fields pointing to document _id values.
        """,
    ),
) -> Dict[str, Any]:
    return await collection_agent.arun(
        {
            "operation": "create_collection",
            "database_name": database_name,
            "collection_name": collection_name,
            "collection_type": collection_type,
        }
    )


@mcp_app.tool(
    name="delete-collection",
    description="""Permanently deletes a collection and all its documents.
    
    ⚠️  WARNING: This operation is irreversible and will:
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
        
        ⚠️  DANGER: All data in this collection will be lost forever.
        
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
