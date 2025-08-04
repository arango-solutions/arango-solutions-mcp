from typing import Any, Dict, List, Optional

from pydantic import Field

from ..agents.graph_management_agent import GraphManagementAgent
from ..server import mcp_app

graph_agent = GraphManagementAgent()


@mcp_app.tool(
    name="list-graphs", description="Lists all graphs in a specified ArangoDB database."
)
async def list_graphs(
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
    )
) -> Dict[str, Any]:
    return await graph_agent.arun(
        {"operation": "list_graphs", "database_name": database_name}
    )


@mcp_app.tool(
    name="create-graph",
    description="Creates a new named graph with vertex and edge collections.",
)
async def create_graph(
    graph_name: str = Field(description="The name for the new graph."),
    edge_definitions: List[Dict[str, Any]] = Field(
        description="A list of edge definition objects. Each object must contain 'edge_collection', 'from_vertex_collections', and 'to_vertex_collections' keys. Example: [{'edge_collection': 'connections', 'from_vertex_collections': ['users'], 'to_vertex_collections': ['companies']}]"
    ),
    orphan_collections: Optional[List[str]] = Field(
        default=None,
        description="Optional. List of additional vertex collections part of the graph but not in an edge definition.",
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
    ),
) -> Dict[str, Any]:
    return await graph_agent.arun(
        {
            "operation": "create_graph",
            "database_name": database_name,
            "graph_name": graph_name,
            "edge_definitions": edge_definitions,
            "orphan_collections": orphan_collections,
        }
    )


@mcp_app.tool(
    name="delete-graph",
    description="Removes an existing graph from a specified ArangoDB database.",
)
async def delete_graph(
    graph_name: str = Field(description="The name of the graph to delete."),
    drop_collections: bool = Field(
        default=False,
        description="Optional. If true, drops the graph's collections as well. Default is false.",
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
    ),
) -> Dict[str, Any]:
    return await graph_agent.arun(
        {
            "operation": "delete_graph",
            "database_name": database_name,
            "graph_name": graph_name,
            "drop_collections": drop_collections,
        }
    )


@mcp_app.tool(
    name="create-edge",
    description="Creates an edge document in a specified edge collection within a graph.",
)
async def create_edge(
    graph_name: str = Field(
        description="The name of the graph containing the edge collection."
    ),
    edge_collection_name: str = Field(
        description="The name of the edge collection where the edge will be created."
    ),
    from_vertex_id: str = Field(description="The _id of the 'from' vertex document."),
    to_vertex_id: str = Field(description="The _id of the 'to' vertex document."),
    edge_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional. Additional attributes for the edge document.",
    ),
    database_name: Optional[str] = Field(
        default=None, description="Optional. Database name."
    ),
) -> Dict[str, Any]:
    return await graph_agent.arun(
        {
            "operation": "create_edge",
            "database_name": database_name,
            "graph_name": graph_name,
            "edge_collection_name": edge_collection_name,
            "from_vertex_id": from_vertex_id,
            "to_vertex_id": to_vertex_id,
            "edge_data": edge_data,
        }
    )
