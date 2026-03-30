import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import GraphCreateError, GraphDeleteError, GraphListError

from agents.agent_base import ArangoAgentBase, handle_arango_errors
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class GraphManagementAgent(ArangoAgentBase):
    """Agent for managing ArangoDB named graphs, including SmartGraphs."""

    @handle_arango_errors(
        "GraphManagementAgent",
        "ArangoDB Graph",
        (GraphListError, GraphCreateError, GraphDeleteError),
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")
        graph_name: Optional[str] = mcp_tool_inputs.get("graph_name")

        edge_definitions: Optional[List[Dict[str, Any]]] = mcp_tool_inputs.get("edge_definitions")
        orphan_collections: Optional[List[str]] = mcp_tool_inputs.get("orphan_collections")

        edge_collection_name: Optional[str] = mcp_tool_inputs.get("edge_collection_name")
        from_vertex_id: Optional[str] = mcp_tool_inputs.get("from_vertex_id")
        to_vertex_id: Optional[str] = mcp_tool_inputs.get("to_vertex_id")
        edge_data: Optional[Dict[str, Any]] = mcp_tool_inputs.get("edge_data")

        # SmartGraph / EnterpriseGraph parameters
        smart: Optional[bool] = mcp_tool_inputs.get("smart")
        disjoint: Optional[bool] = mcp_tool_inputs.get("disjoint")
        smart_field: Optional[str] = mcp_tool_inputs.get("smart_field")
        shard_count: Optional[int] = mcp_tool_inputs.get("shard_count")
        replication_factor: Optional[int] = mcp_tool_inputs.get("replication_factor")
        write_concern: Optional[int] = mcp_tool_inputs.get("write_concern")
        satellite_collections: Optional[List[str]] = mcp_tool_inputs.get("satellite_collections")
        is_satellite: Optional[bool] = mcp_tool_inputs.get("is_satellite")

        logger.info(
            f"GraphManagementAgent: Op='{operation}', DB='{database_name}', Graph='{graph_name}'"
        )

        db = arango_connector.get_db(database_name)
        database_name = database_name or db.name

        if operation == "list_graphs":
            graphs = db.graphs()
            return {"graphs": graphs}

        elif operation == "create_graph":
            if not graph_name or not edge_definitions:
                return {"error": "Graph name and edge definitions are required for graph creation."}
            if db.has_graph(graph_name):
                return {
                    "status": f"Graph '{graph_name}' already exists in database '{database_name}'."
                }

            create_kwargs: Dict[str, Any] = {
                "edge_definitions": edge_definitions,
                "orphan_collections": orphan_collections or [],
            }

            if smart is not None:
                create_kwargs["smart"] = smart
            if disjoint is not None:
                create_kwargs["disjoint"] = disjoint
            if smart_field is not None:
                create_kwargs["smart_field"] = smart_field
            if shard_count is not None:
                create_kwargs["shard_count"] = shard_count
            if replication_factor is not None:
                create_kwargs["replication_factor"] = replication_factor
            if write_concern is not None:
                create_kwargs["write_concern"] = write_concern
            if satellite_collections is not None:
                create_kwargs["satellite_collections"] = satellite_collections

            # SatelliteGraph: set replication_factor to "satellite"
            if is_satellite:
                create_kwargs["replication_factor"] = "satellite"

            graph_obj = db.create_graph(graph_name, **create_kwargs)
            return {
                "status": f"Graph '{graph_name}' created successfully.",
                "graph_info": graph_obj.properties(),
            }

        elif operation == "get_graph_properties":
            if not graph_name:
                return {"error": "Graph name is required."}
            if not db.has_graph(graph_name):
                return {"error": f"Graph '{graph_name}' not found in database '{database_name}'."}
            graph_obj = db.graph(graph_name)
            return {"properties": graph_obj.properties()}

        elif operation == "delete_graph":
            if not graph_name:
                return {"error": "Graph name is required for deletion."}
            if not db.has_graph(graph_name):
                return {"error": f"Graph '{graph_name}' not found in database '{database_name}'."}

            db.delete_graph(
                graph_name,
                ignore_missing=False,
                drop_collections=mcp_tool_inputs.get("drop_collections", False),
            )
            return {"status": f"Graph '{graph_name}' deleted successfully."}

        elif operation == "create_edge":
            if not graph_name or not edge_collection_name or not from_vertex_id or not to_vertex_id:
                return {
                    "error": "Graph name, edge collection name, from_vertex_id, and to_vertex_id are required to create an edge."
                }
            if not db.has_graph(graph_name):
                return {"error": f"Graph '{graph_name}' not found."}

            graph_obj = db.graph(graph_name)
            if not graph_obj.has_edge_definition(edge_collection_name):
                return {
                    "error": f"Edge collection '{edge_collection_name}' not part of graph '{graph_name}' definitions."
                }

            edge_collection = graph_obj.edge_collection(edge_collection_name)

            edge_document_to_insert = edge_data or {}
            edge_document_to_insert["_from"] = from_vertex_id
            edge_document_to_insert["_to"] = to_vertex_id

            meta = edge_collection.insert(edge_document_to_insert)
            return {"status": "Edge created successfully.", "edge_metadata": meta}

        else:
            return {"error": f"Unknown graph operation: {operation}"}
