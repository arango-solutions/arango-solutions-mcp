from typing import Any, Dict, List, Optional

from pydantic import Field

from ..agents.index_management_agent import IndexManagementAgent
from ..server import mcp_app

index_agent = IndexManagementAgent()


@mcp_app.tool(
    name="list-indexes", description="Lists all indexes for a specified collection."
)
async def list_indexes(
    collection_name: str = Field(description="The name of the collection."),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
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
    description="Adds a new index to a collection based on the provided definition.",
)
async def create_index(
    collection_name: str = Field(description="The name of the collection."),
    index_definition: Dict[str, Any] = Field(
        description="The index definition as a JSON object. E.g., {'type': 'persistent', 'fields': ['name'], 'unique': True}"
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
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
    description="Removes an existing index from a collection by its ID or name.",
)
async def delete_index(
    collection_name: str = Field(description="The name of the collection."),
    index_id_or_name: str = Field(description="The ID or name of the index to delete."),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
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
