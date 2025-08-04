from typing import Any, Dict, List, Optional, Union  # Union for properties

from pydantic import Field

from ..agents.analyzer_management_agent import AnalyzerManagementAgent
from ..server import mcp_app

analyzer_agent = AnalyzerManagementAgent()


@mcp_app.tool(
    name="list-analyzers",
    description="Lists all available analyzers in a specified ArangoDB database.",
)
async def list_analyzers(
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
    )
) -> Dict[str, Any]:
    return await analyzer_agent.arun(
        {"operation": "list_analyzers", "database_name": database_name}
    )


@mcp_app.tool(
    name="create-analyzer",
    description="Creates a new custom analyzer for text processing.",
)
async def create_analyzer(
    analyzer_name: str = Field(
        description="The name for the new analyzer (e.g., 'my_text_analyzer')."
    ),
    analyzer_type: str = Field(
        description="The type of the analyzer (e.g., 'identity', 'text', 'ngram', 'delimiter')."
    ),
    properties: Optional[Union[Dict[str, Any], str]] = Field(
        default=None,
        description="Analyzer-specific properties. For 'text' type, it's a dict like {'locale': 'en.utf-8', 'stopwords': []}. For 'ngram', it can be like {'minN': 2, 'maxN': 3, 'preserveOriginal': True} or a string for N-Gram stream type like 'binary'/'utf8'.",
    ),
    features: Optional[List[str]] = Field(
        default=None,
        description="Optional. List of features to enable for the analyzer (e.g., ['frequency', 'norm', 'position']).",
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
    ),
) -> Dict[str, Any]:
    return await analyzer_agent.arun(
        {
            "operation": "create_analyzer",
            "database_name": database_name,
            "analyzer_name": analyzer_name,
            "analyzer_type": analyzer_type,
            "properties": properties,
            "features": features,
        }
    )


@mcp_app.tool(
    name="delete-analyzer",
    description="Removes an existing analyzer from a specified ArangoDB database.",
)
async def delete_analyzer(
    analyzer_name: str = Field(description="The name of the analyzer to delete."),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
    ),
) -> Dict[str, Any]:
    return await analyzer_agent.arun(
        {
            "operation": "delete_analyzer",
            "database_name": database_name,
            "analyzer_name": analyzer_name,
        }
    )


@mcp_app.tool(
    name="get-analyzer-properties",
    description="Retrieves the definition (configuration and features) of a specific analyzer.",
)  # Changed from get_analyzer_properties
async def get_analyzer_definition(  # Renamed function for clarity
    analyzer_name: str = Field(description="The name of the analyzer to inspect."),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
    ),
) -> Dict[str, Any]:
    return await analyzer_agent.arun(
        {
            "operation": "get_analyzer_properties",  # Agent operation name remains the same
            "database_name": database_name,
            "analyzer_name": analyzer_name,
        }
    )
