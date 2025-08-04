from typing import (  # List removed as it's not directly used for type hints here
    Any, Dict, Optional)

from pydantic import Field

from ..agents.collection_management_agent import CollectionManagementAgent
from ..server import mcp_app

collection_agent = CollectionManagementAgent()


@mcp_app.tool(
    name="list-collections",
    description="Lists all user-defined (non-system) collections in a specified ArangoDB database (or the default database). System collections starting with '_' are excluded.",
)
async def list_collections(
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The name of the database. Defaults to the server's default database.",
    )
) -> Dict[str, Any]:
    return await collection_agent.arun(
        {"operation": "list_collections", "database_name": database_name}
    )


@mcp_app.tool(
    name="create-collection",
    description="Creates a new standard (document) or edge collection in a specified ArangoDB database.",
)
async def create_collection(
    collection_name: str = Field(description="The name for the new collection."),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The name of the database. Defaults to the server's default database.",
    ),
    collection_type: str = Field(
        default="document",
        description="Type of collection: 'document' (default) or 'edge'.",
    ),  # Vertex collections are standard collections
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
    description="Deletes an existing collection from a specified ArangoDB database.",
)
async def delete_collection(
    collection_name: str = Field(description="The name of the collection to delete."),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The name of the database. Defaults to the server's default database.",
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
    description="Retrieves properties, document count, and statistics for a specified collection.",
)
async def get_collection_properties(
    collection_name: str = Field(description="The name of the collection to inspect."),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The name of the database. Defaults to the server's default database.",
    ),
) -> Dict[str, Any]:
    return await collection_agent.arun(
        {
            "operation": "get_collection_properties",
            "database_name": database_name,
            "collection_name": collection_name,
        }
    )
