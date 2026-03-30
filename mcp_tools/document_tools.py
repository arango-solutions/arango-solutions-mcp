from typing import Any, Dict, List, Optional

from pydantic import Field

from agents.document_crud_agent import DocumentCRUDAgent
from server import mcp_app

doc_agent = DocumentCRUDAgent()


@mcp_app.tool(
    name="create-document",
    description="""Creates a new document in an ArangoDB collection.
    
    Documents in ArangoDB are JSON objects that can contain:
    - Nested objects and arrays
    - Various data types (strings, numbers, booleans, null)
    - Automatic _key and _id generation if not provided
    - Custom metadata and business logic
    
    Use this for:
    - Adding new records to your application
    - Storing user profiles, products, orders, etc.
    - Creating nodes in graph structures
    - Logging events and transactions
    
    Best practices:
    - Include meaningful field names
    - Consider indexing frequently queried fields
    - Use consistent data schemas within collections
    - Validate required fields before insertion
    """,
)
async def create_document(
    collection_name: str = Field(
        description="""Name of the collection where the document will be stored.
        
        Examples:
        - 'users' - for user profiles
        - 'products' - for product catalog
        - 'orders' - for e-commerce orders
        - 'events' - for event logging
        
        The collection must already exist. Use 'create-collection' first if needed.
        """
    ),
    document_data: Dict[str, Any] = Field(
        description="""The document content as a JSON object.
        
        Examples:
        - User: {"name": "John Doe", "email": "john@example.com", "age": 30, "active": true}
        - Product: {"title": "Laptop", "price": 999.99, "category": "electronics", "tags": ["computer", "portable"]}
        - Order: {"user_id": "123", "items": [{"product": "abc", "qty": 2}], "total": 199.98, "date": "2023-12-01"}
        
        Special fields:
        - '_key': Custom document key (optional, auto-generated if not provided)
        - '_id': Full document ID in format 'collection/key' (auto-generated)
        - '_rev': Revision ID (managed by ArangoDB)
        
        Avoid using field names starting with underscore except for system fields.
        """
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="""Target database name. Uses default database if not specified.
        
        Examples:
        - 'myapp' - application database
        - 'analytics' - analytics data
        - 'staging' - staging environment
        """,
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "create_document",
            "database_name": database_name,
            "collection_name": collection_name,
            "document_data": document_data,
        }
    )


@mcp_app.tool(
    name="create-documents-bulk",
    description="""Efficiently inserts multiple documents into a collection in a single operation.
    
    Bulk operations provide:
    - Better performance for large datasets
    - Reduced network overhead
    - Atomic batch processing
    - Detailed success/failure reporting per document
    
    Use this for:
    - Data migration and imports
    - Batch processing workflows
    - Loading sample or seed data
    - High-throughput data ingestion
    
    Performance tips:
    - Use batches of 100-1000 documents for optimal performance
    - Ensure consistent document schemas
    - Pre-create indexes for frequently queried fields
    """,
)
async def create_documents_bulk(
    collection_name: str = Field(
        description="""Name of the target collection for bulk insertion.
        
        Examples:
        - 'products' - for product catalog import
        - 'users' - for user data migration
        - 'transactions' - for financial data batch
        """
    ),
    documents_data: List[Dict[str, Any]] = Field(
        description="""Array of document objects to insert.
        
        Examples:
        - User batch: [{"name": "Alice", "email": "alice@example.com"}, {"name": "Bob", "email": "bob@example.com"}]
        - Product batch: [{"title": "Laptop", "price": 999}, {"title": "Mouse", "price": 29}]
        
        Each document follows the same format as single document creation.
        Recommendation: Keep batches under 1000 documents for optimal performance.
        
        Response will include details about successful and failed insertions.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "create_documents_bulk",
            "database_name": database_name,
            "collection_name": collection_name,
            "documents_data": documents_data,
        }
    )


@mcp_app.tool(
    name="read-document",
    description="""Retrieves a single document by its unique identifier.
    
    ArangoDB documents have unique identifiers:
    - '_key': Unique within collection (e.g., 'user123', 'ABC-456')
    - '_id': Global unique ID in format 'collection/key' (e.g., 'users/user123')
    
    Use this for:
    - Getting user profiles by ID
    - Retrieving specific products or orders
    - Loading configuration documents
    - Fetching individual records for editing
    
    Performance: Document lookups by key/ID are extremely fast (O(1)) due to indexing.
    """,
)
async def read_document(
    collection_name: str = Field(
        description="""Name of the collection containing the document.
        
        Examples:
        - 'users' - to retrieve user profiles
        - 'products' - to get product details
        - 'orders' - to fetch order information
        """
    ),
    document_key_or_id: str = Field(
        description="""Document identifier - either _key or full _id.
        
        Examples:
        - Key format: 'user123', 'ABC-456', 'order_2023_001'
        - ID format: 'users/user123', 'products/ABC-456'
        
        Both formats work, but _key is more common for single-collection operations.
        Use _id format when working across multiple collections.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "read_document",
            "database_name": database_name,
            "collection_name": collection_name,
            "document_key_or_id": document_key_or_id,
        }
    )


@mcp_app.tool(
    name="read-documents-with-filter",
    description="""Queries documents from a collection using simple filter conditions.
    
    This provides basic filtering capabilities similar to MongoDB's find() or SQL WHERE clauses.
    For complex operations like joins, graph traversals, or advanced analytics, use 'execute-aql-query' instead.
    
    Supported filter operations:
    - Equality: {"status": "active", "category": "electronics"}
    - Range queries work with proper indexing
    - Array membership and nested field access
    
    Use this for:
    - Simple document searches
    - Filtering by status, category, or type
    - Basic pagination and limiting
    - Quick data exploration
    
    For complex needs like sorting, joins, or aggregations, use AQL queries instead.
    """,
)
async def read_documents_with_filter(
    collection_name: str = Field(
        description="""Name of the collection to query.
        
        Examples:
        - 'products' - to search product catalog
        - 'users' - to find users by criteria
        - 'orders' - to filter orders
        """
    ),
    filters: Dict[str, Any] = Field(
        description="""Filter conditions as key-value pairs.
        
        Examples:
        - Simple: {"status": "active", "category": "electronics"}
        - Multiple: {"age": 25, "city": "New York", "verified": true}
        - Nested: {"address.country": "USA", "profile.premium": true}
        
        Note: This uses simple equality matching. For range queries (>, <, BETWEEN),
        regex patterns, or complex logic, use the 'execute-aql-query' tool instead.
        
        All conditions are combined with AND logic.
        """
    ),
    limit: int = Field(
        default=100,
        description="""Maximum number of documents to return (1-1000).
        
        Use for pagination and performance:
        - Small collections: 100-500
        - Large collections: 50-200
        - Real-time queries: 10-50
        """,
    ),
    skip: int = Field(
        default=0,
        description="""Number of documents to skip (for pagination).
        
        Examples:
        - Page 1: skip=0, limit=20
        - Page 2: skip=20, limit=20
        - Page 3: skip=40, limit=20
        """,
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "read_documents_filter",
            "database_name": database_name,
            "collection_name": collection_name,
            "filters": filters,
            "limit": limit,
            "skip": skip,
        }
    )


@mcp_app.tool(
    name="update-document",
    description="""Partially updates an existing document, merging new data with existing fields.
    
    Update behavior:
    - Existing fields are preserved unless explicitly overwritten
    - New fields are added to the document
    - Use null values to remove fields
    - _rev is automatically updated for conflict detection
    
    Use this for:
    - Updating user profiles or preferences
    - Modifying product information
    - Changing order status or details
    - Incrementing counters or statistics
    
    Safety: Document must exist or operation will fail.
    For upsert behavior (create if not exists), consider using AQL UPSERT.
    """,
)
async def update_document(
    collection_name: str = Field(
        description="""Name of the collection containing the document to update.
        
        Examples:
        - 'users' - for user profile updates
        - 'products' - for product information changes
        - 'orders' - for order status updates
        """
    ),
    document_data: Dict[str, Any] = Field(
        description="""Document data including identifier and fields to update.
        
        REQUIRED: Must include either '_key' or '_id' to identify the document.
        
        Examples:
        - Update user email: {"_key": "user123", "email": "newemail@example.com"}
        - Update product price: {"_key": "product456", "price": 199.99, "sale": true}
        - Update order status: {"_id": "orders/order789", "status": "shipped", "tracking": "TRACK123"}
        - Add nested data: {"_key": "user123", "preferences.theme": "dark", "preferences.notifications": false}
        
        Only the specified fields will be updated. Existing fields remain unchanged.
        Set field to null to remove it from the document.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "update_document",
            "database_name": database_name,
            "collection_name": collection_name,
            "document_data": document_data,
        }
    )


@mcp_app.tool(
    name="delete-document",
    description="""Permanently deletes a single document from a collection.

    WARNING: This operation is irreversible. The document and all its data
    will be permanently removed.

    Use this for:
    - Removing specific records (user accounts, expired entries)
    - Cleaning up test data
    - GDPR/compliance data deletion

    The document must exist or the operation will fail.
    For bulk deletion, use the 'execute-aql-query' tool with a REMOVE statement.
    """,
)
async def delete_document(
    collection_name: str = Field(
        description="Name of the collection containing the document to delete."
    ),
    document_key_or_id: str = Field(
        description="""Document identifier - either _key or full _id.

        Examples:
        - Key: 'user123'
        - ID: 'users/user123'
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "delete_document",
            "database_name": database_name,
            "collection_name": collection_name,
            "document_key_or_id": document_key_or_id,
        }
    )


@mcp_app.tool(
    name="replace-document",
    description="""Completely replaces a document with new content.

    Unlike 'update-document' (which merges), replace overwrites the entire
    document body. Only _key, _id, and _rev are preserved from the original.

    Use this when you need to set the document to an exact known state
    rather than partially patching fields.
    """,
)
async def replace_document(
    collection_name: str = Field(
        description="Name of the collection containing the document to replace."
    ),
    document_data: Dict[str, Any] = Field(
        description="""Complete replacement document. Must include _key or _id.

        Example:
        {"_key": "user123", "name": "Jane Doe", "email": "jane@new.com", "role": "admin"}

        All previous fields not in this payload will be removed.
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "replace_document",
            "database_name": database_name,
            "collection_name": collection_name,
            "document_data": document_data,
        }
    )


@mcp_app.tool(
    name="upsert-document",
    description="""Insert a document if it doesn't exist, or update it if it does.

    Atomically searches for a document matching search_fields. If found, merges
    update_data into the existing document. If not found, inserts document_data
    as a new document.

    Use this for:
    - Idempotent data ingestion (safe to retry without duplicates)
    - Sync / import pipelines where records may already exist
    - Counters and accumulators (increment on match, initialize on miss)
    """,
)
async def upsert_document(
    collection_name: str = Field(description="Name of the collection for the upsert operation."),
    search_fields: Dict[str, Any] = Field(
        description="""Fields to match when looking for an existing document.

        Example: {"email": "alice@example.com"}
        If a document with this email exists, it will be updated.
        """
    ),
    document_data: Dict[str, Any] = Field(
        description="""Document to INSERT if no match is found.

        Example: {"email": "alice@example.com", "name": "Alice", "role": "user"}
        """
    ),
    update_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="""Fields to UPDATE if a match IS found (merge semantics).
        If omitted, document_data is used for both insert and update.

        Example: {"last_seen": "2024-01-15", "login_count": 42}
        """,
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "upsert_document",
            "database_name": database_name,
            "collection_name": collection_name,
            "search_fields": search_fields,
            "document_data": document_data,
            "update_data": update_data,
        }
    )


@mcp_app.tool(
    name="update-documents-bulk",
    description="""Partially updates multiple documents in a single operation.

    Each document in the list must include _key or _id to identify
    the target. Other fields are merged into the existing document.
    Returns per-document results (success or error for each).
    """,
)
async def update_documents_bulk(
    collection_name: str = Field(
        description="Name of the collection containing the documents to update."
    ),
    documents_data: List[Dict[str, Any]] = Field(
        description="""Array of partial documents, each with _key or _id plus fields to update.

        Example:
        [
          {"_key": "user1", "status": "active"},
          {"_key": "user2", "status": "suspended", "reason": "TOS violation"}
        ]
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "update_documents_bulk",
            "database_name": database_name,
            "collection_name": collection_name,
            "documents_data": documents_data,
        }
    )


@mcp_app.tool(
    name="delete-documents-bulk",
    description="""Deletes multiple documents from a collection in a single operation.

    Each entry must include _key or _id to identify the document to remove.
    Returns per-document results. Faster than individual deletes for batch cleanup.

    WARNING: This is irreversible for each successfully deleted document.
    """,
)
async def delete_documents_bulk(
    collection_name: str = Field(
        description="Name of the collection containing the documents to delete."
    ),
    documents_data: List[Dict[str, Any]] = Field(
        description="""Array of document identifiers to delete.

        Example:
        [{"_key": "old_user_1"}, {"_key": "old_user_2"}, {"_key": "old_user_3"}]
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await doc_agent.arun(
        {
            "operation": "delete_documents_bulk",
            "database_name": database_name,
            "collection_name": collection_name,
            "documents_data": documents_data,
        }
    )
