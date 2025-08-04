from typing import Any, Dict, List, Optional

from pydantic import Field

from ..agents.document_crud_agent import DocumentCRUDAgent
from ..server import mcp_app

doc_agent = DocumentCRUDAgent()


@mcp_app.tool(
    name="create-document",
    description="Inserts a single new document into a specified collection.",
)
async def create_document(
    collection_name: str = Field(description="The name of the collection."),
    document_data: Dict[str, Any] = Field(
        description="The document content as a JSON object."
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
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
    description="Inserts multiple documents into a collection in bulk.",
)
async def create_documents_bulk(
    collection_name: str = Field(description="The name of the collection."),
    documents_data: List[Dict[str, Any]] = Field(
        description="A list of document objects."
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
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
    name="read-document", description="Retrieves a single document by its _key or _id."
)
async def read_document(
    collection_name: str = Field(description="The name of the collection."),
    document_key_or_id: str = Field(
        description="The _key or _id of the document to retrieve."
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
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
    description="Queries multiple documents from a collection based on a filter. For sorting or complex queries, use 'execute-aql-query'.",
)
async def read_documents_with_filter(
    collection_name: str = Field(description="The name of the collection."),
    filters: Dict[str, Any] = Field(
        description="A JSON object representing the filter conditions (e.g., {'age': 30, 'city': 'New York'})."
    ),
    # sort_by: Optional[str] = Field(default=None, description="Optional. Field name to sort by."),
    # sort_order: str = Field(default="ASC", description="Optional. Sort order: 'ASC' or 'DESC'."),
    limit: int = Field(
        default=100, description="Optional. Maximum number of documents to return."
    ),
    skip: int = Field(default=0, description="Optional. Number of documents to skip."),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
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
    description="Partially updates a single existing document. Requires _key or _id in document_data.",
)
async def update_document(
    collection_name: str = Field(description="The name of the collection."),
    document_data: Dict[str, Any] = Field(
        description="A JSON object containing the document's _key or _id and fields to update."
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
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
