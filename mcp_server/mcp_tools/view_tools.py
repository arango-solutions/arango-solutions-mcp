# mcp_server/mcp_tools/view_tools.py
from typing import Any, Dict, List, Optional

from pydantic import Field

from ..agents.view_management_agent import ViewManagementAgent
from ..server import mcp_app

view_agent = ViewManagementAgent()

ARANGOSEARCH_PROPERTIES_EXAMPLE = """
Example for 'arangosearch' view type when adding links:
{
  "cleanupIntervalStep": 2, // Optional, ArangoDB has defaults
  "consolidationIntervalMsec": 1000, // Optional
  "links": {
    "your_collection_name": { // Replace with actual collection name
      "analyzers": ["text_en", "identity"], // Ensure these analyzers exist
      "fields": {
        "field_to_search_with_text_analyzer": { "analyzers": ["text_en"] },
        "field_for_exact_filter": { "analyzers": ["identity"] }
      },
      "includeAllFields": false, // Set to true to include all fields by default
      "storeValues": "id", // "id", "full", or "none"
      "trackListPositions": false // For array field indexing
    }
    // Add more collections here if needed
  }
}
"""

SEARCHALIAS_PROPERTIES_EXAMPLE = """
Example for 'search-alias' view type (requires an existing inverted index on the collection):
{
  "indexes": [
    {
      "collection": "source_collection_name", // Replace with actual collection name
      "index": "inverted_index_name_on_source_collection" // Replace with actual index name
    }
    // Add more index links here if needed
  ]
}
"""


@mcp_app.tool(
    name="list-views",
    description="Lists all views in a specified ArangoDB database or the default database.",
)
async def list_views(
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The name of the database. If not provided, the server's default database will be used.",
    )
) -> Dict[str, Any]:
    return await view_agent.arun(
        {"operation": "list_views", "database_name": database_name}
    )


@mcp_app.tool(
    name="create-view",
    description="Creates a new view. For 'arangosearch', properties (especially links) can be minimal initially and added later via 'update-view-properties' or 'replace-view-properties'. For 'search-alias', 'properties' with index links are required.",
)
async def create_view(
    view_name: str = Field(description="The unique name for the new view."),
    view_type: str = Field(
        description="The type of the view to create. Supported: 'arangosearch', 'search-alias'."
    ),
    properties: Optional[Dict[str, Any]] = Field(
        default=None,
        description=f"Optional for 'arangosearch' initial creation, required for 'search-alias'. A JSON object detailing the view's configuration. \nFor 'arangosearch' (if providing links):\n{ARANGOSEARCH_PROPERTIES_EXAMPLE}\nFor 'search-alias' (required):\n{SEARCHALIAS_PROPERTIES_EXAMPLE}",
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The database where the view will be created. Defaults to the server's configured default database.",
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {
            "operation": "create_view",
            "database_name": database_name,
            "view_name": view_name,
            "view_type": view_type,
            "properties": properties,  # Pass None if user doesn't provide it
        }
    )


@mcp_app.tool(
    name="get-view-properties",
    description="Retrieves the current properties and definition of a specific view.",
)
async def get_view_properties(
    view_name: str = Field(
        description="The name of the view whose properties are to be retrieved."
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The database where the view resides. Defaults to the server's default database.",
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {
            "operation": "get_view_properties",
            "database_name": database_name,
            "view_name": view_name,
        }
    )


@mcp_app.tool(
    name="update-view-properties",
    description="Partially modifies the properties of an existing view. Only specified properties are changed. Use this to add/modify links for ArangoSearch views after creation.",
)
async def update_view_properties(
    view_name: str = Field(description="The name of the view to update."),
    properties: Dict[str, Any] = Field(
        description=f"A JSON object containing only the properties to be updated and their new values. \nFor ArangoSearch links:\n{ARANGOSEARCH_PROPERTIES_EXAMPLE}\nFor SearchAlias (if updatable properties exist):\n{SEARCHALIAS_PROPERTIES_EXAMPLE}"
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The database of the view. Defaults to the server's default database.",
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {
            "operation": "update_view_properties",
            "database_name": database_name,
            "view_name": view_name,
            "properties": properties,
        }
    )


@mcp_app.tool(
    name="replace-view-properties",
    description="Completely replaces all properties of an existing view with a new set. Properties not included in the input will be reset to their defaults or removed. Use this to define the full configuration for ArangoSearch or SearchAlias views.",
)
async def replace_view_properties(
    view_name: str = Field(
        description="The name of the view whose properties will be replaced."
    ),
    properties: Dict[str, Any] = Field(
        description=f"A JSON object representing the complete new set of properties for the view. Structure depends on view type.\nFor ArangoSearch:\n{ARANGOSEARCH_PROPERTIES_EXAMPLE}\nFor SearchAlias:\n{SEARCHALIAS_PROPERTIES_EXAMPLE}"
    ),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The database of the view. Defaults to the server's default database.",
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {
            "operation": "replace_view_properties",
            "database_name": database_name,
            "view_name": view_name,
            "properties": properties,
        }
    )


@mcp_app.tool(
    name="delete-view", description="Removes an existing view from the database."
)
async def delete_view(
    view_name: str = Field(description="The name of the view to be deleted."),
    database_name: Optional[str] = Field(
        default=None,
        description="Optional. The database from which to delete the view. Defaults to the server's default database.",
    ),
) -> Dict[str, Any]:
    return await view_agent.arun(
        {
            "operation": "delete_view",
            "database_name": database_name,
            "view_name": view_name,
        }
    )
