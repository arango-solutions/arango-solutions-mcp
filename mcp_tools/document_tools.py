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
        
        Collection will be created automatically if it doesn't exist.
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
            # "sort_by": sort_by,
            # "sort_order": sort_order,
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
