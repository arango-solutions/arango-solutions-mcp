import logging
from typing import Any, Dict, Optional

from arango.exceptions import AQLQueryExecuteError, ArangoServerError

from agents.agent_base import ArangoAgentBase
from aql_utils import validate_aql_identifier, validate_aql_identifiers
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class GraphTraversalAgent(ArangoAgentBase):
    """Agent for ArangoDB graph traversals, shortest paths, and neighbor queries.

    Generates and executes AQL traversal queries against named graphs
    or edge collections directly.
    """

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")

        logger.info(f"GraphTraversalAgent: Op='{operation}', DB='{database_name}'")

        try:
            db = arango_connector.get_db(database_name)
            database_name = database_name or db.name

            if operation == "traverse":
                return self._traverse(db, mcp_tool_inputs)
            elif operation == "shortest_path":
                return self._shortest_path(db, mcp_tool_inputs)
            elif operation == "k_shortest_paths":
                return self._k_shortest_paths(db, mcp_tool_inputs)
            elif operation == "neighbors":
                return self._neighbors(db, mcp_tool_inputs)
            else:
                return {"error": f"Unknown traversal operation: {operation}"}

        except AQLQueryExecuteError as e:
            logger.error(f"GraphTraversalAgent: AQL error - {e}")
            return {
                "error": f"AQL Execution Error: {e.error_message}",
                "error_code": e.error_code,
            }
        except ArangoServerError as e:
            logger.error(f"GraphTraversalAgent: ArangoDB error - {e}")
            return {
                "error": f"ArangoDB Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"GraphTraversalAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}

    def _validate_direction(self, direction: str) -> Optional[str]:
        d = direction.upper()
        if d in ("OUTBOUND", "INBOUND", "ANY"):
            return d
        return None

    def _build_graph_source(self, inputs: Dict[str, Any]) -> Optional[str]:
        """Build GRAPH 'name' or edge collection list clause."""
        graph_name = inputs.get("graph_name")
        edge_collections = inputs.get("edge_collections")
        if graph_name:
            validate_aql_identifier(graph_name, "graph_name")
            return f"GRAPH '{graph_name}'"
        elif edge_collections:
            validate_aql_identifiers(edge_collections, "edge_collection")
            return ", ".join(f"`{ec}`" for ec in edge_collections)
        return None

    def _traverse(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        start_vertex: str = inputs.get("start_vertex", "")
        direction: str = inputs.get("direction", "OUTBOUND")
        min_depth: int = inputs.get("min_depth", 1)
        max_depth: int = inputs.get("max_depth", 1)
        limit: int = inputs.get("limit", 100)
        vertex_filters: Optional[Dict[str, Any]] = inputs.get("vertex_filters")
        edge_filters: Optional[Dict[str, Any]] = inputs.get("edge_filters")
        return_vertices: bool = inputs.get("return_vertices", True)
        return_edges: bool = inputs.get("return_edges", True)
        return_paths: bool = inputs.get("return_paths", False)

        if not start_vertex:
            return {"error": "start_vertex is required (format: 'collection/key')."}

        dir_str = self._validate_direction(direction)
        if not dir_str:
            return {"error": f"Invalid direction '{direction}'. Use OUTBOUND, INBOUND, or ANY."}

        graph_source = self._build_graph_source(inputs)
        if not graph_source:
            return {"error": "Either graph_name or edge_collections is required."}

        if vertex_filters:
            validate_aql_identifiers(list(vertex_filters.keys()), "vertex_filter_key")
        if edge_filters:
            validate_aql_identifiers(list(edge_filters.keys()), "edge_filter_key")

        bind_vars: Dict[str, Any] = {
            "start": start_vertex,
            "minD": int(min_depth),
            "maxD": int(max_depth),
            "lim": int(limit),
        }

        # Build filter clauses
        filter_lines = []
        if vertex_filters:
            for i, (key, val) in enumerate(vertex_filters.items()):
                vname = f"vf{i}"
                filter_lines.append(f"FILTER v.`{key}` == @{vname}")
                bind_vars[vname] = val
        if edge_filters:
            for i, (key, val) in enumerate(edge_filters.items()):
                ename = f"ef{i}"
                filter_lines.append(f"FILTER e.`{key}` == @{ename}")
                bind_vars[ename] = val

        filters_block = "\n  ".join(filter_lines)
        filters_str = f"\n  {filters_block}" if filters_block else ""

        # Build return expression
        return_parts = []
        if return_vertices:
            return_parts.append('"vertex": v')
        if return_edges:
            return_parts.append('"edge": e')
        if return_paths:
            return_parts.append('"path": p')
        if not return_parts:
            return_parts.append('"vertex": v')
        return_expr = "{ " + ", ".join(return_parts) + " }"

        aql = (
            f"FOR v, e, p IN @minD..@maxD {dir_str} @start {graph_source}"
            f"{filters_str}\n"
            f"  LIMIT @lim\n"
            f"  RETURN {return_expr}"
        )

        logger.info(f"GraphTraversalAgent: Traversal AQL: {aql[:200]}...")
        cursor = db.aql.execute(aql, bind_vars=bind_vars, count=True)
        results = list(cursor)

        return {
            "results": results,
            "count": len(results),
            "aql_generated": aql,
        }

    def _shortest_path(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        start_vertex: str = inputs.get("start_vertex", "")
        target_vertex: str = inputs.get("target_vertex", "")
        direction: str = inputs.get("direction", "OUTBOUND")
        weight_attribute: Optional[str] = inputs.get("weight_attribute")

        if not start_vertex or not target_vertex:
            return {"error": "Both start_vertex and target_vertex are required."}

        dir_str = self._validate_direction(direction)
        if not dir_str:
            return {"error": f"Invalid direction '{direction}'. Use OUTBOUND, INBOUND, or ANY."}

        graph_source = self._build_graph_source(inputs)
        if not graph_source:
            return {"error": "Either graph_name or edge_collections is required."}

        bind_vars: Dict[str, Any] = {"start": start_vertex, "target": target_vertex}

        options_str = ""
        if weight_attribute:
            validate_aql_identifier(weight_attribute, "weight_attribute")
            options_str = f' OPTIONS {{weightAttribute: "{weight_attribute}", defaultWeight: 1}}'

        aql = (
            f"FOR v, e IN {dir_str} SHORTEST_PATH @start TO @target "
            f"{graph_source}{options_str}\n"
            f"  RETURN {{vertex: v, edge: e}}"
        )

        logger.info(f"GraphTraversalAgent: Shortest path AQL: {aql[:200]}...")
        cursor = db.aql.execute(aql, bind_vars=bind_vars, count=True)
        results = list(cursor)

        return {
            "results": results,
            "path_length": len(results) - 1 if results else 0,
            "aql_generated": aql,
        }

    def _k_shortest_paths(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        start_vertex: str = inputs.get("start_vertex", "")
        target_vertex: str = inputs.get("target_vertex", "")
        direction: str = inputs.get("direction", "OUTBOUND")
        limit: int = inputs.get("limit", 5)
        weight_attribute: Optional[str] = inputs.get("weight_attribute")

        if not start_vertex or not target_vertex:
            return {"error": "Both start_vertex and target_vertex are required."}

        dir_str = self._validate_direction(direction)
        if not dir_str:
            return {"error": f"Invalid direction '{direction}'. Use OUTBOUND, INBOUND, or ANY."}

        graph_source = self._build_graph_source(inputs)
        if not graph_source:
            return {"error": "Either graph_name or edge_collections is required."}

        bind_vars: Dict[str, Any] = {
            "start": start_vertex,
            "target": target_vertex,
            "lim": int(limit),
        }

        options_str = ""
        if weight_attribute:
            validate_aql_identifier(weight_attribute, "weight_attribute")
            options_str = f' OPTIONS {{weightAttribute: "{weight_attribute}", defaultWeight: 1}}'

        aql = (
            f"FOR path IN {dir_str} K_SHORTEST_PATHS @start TO @target "
            f"{graph_source}{options_str}\n"
            f"  LIMIT @lim\n"
            f"  RETURN path"
        )

        logger.info(f"GraphTraversalAgent: K shortest paths AQL: {aql[:200]}...")
        cursor = db.aql.execute(aql, bind_vars=bind_vars, count=True)
        results = list(cursor)

        return {
            "results": results,
            "count": len(results),
            "aql_generated": aql,
        }

    def _neighbors(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        start_vertex: str = inputs.get("start_vertex", "")
        direction: str = inputs.get("direction", "ANY")
        depth: int = inputs.get("depth", 1)
        limit: int = inputs.get("limit", 100)
        vertex_filters: Optional[Dict[str, Any]] = inputs.get("vertex_filters")
        deduplicate: bool = inputs.get("deduplicate", True)

        if not start_vertex:
            return {"error": "start_vertex is required (format: 'collection/key')."}

        dir_str = self._validate_direction(direction)
        if not dir_str:
            return {"error": f"Invalid direction '{direction}'."}

        graph_source = self._build_graph_source(inputs)
        if not graph_source:
            return {"error": "Either graph_name or edge_collections is required."}

        if vertex_filters:
            validate_aql_identifiers(list(vertex_filters.keys()), "vertex_filter_key")

        bind_vars: Dict[str, Any] = {
            "start": start_vertex,
            "depthVal": int(depth),
            "lim": int(limit),
        }

        filter_lines = []
        if vertex_filters:
            for i, (key, val) in enumerate(vertex_filters.items()):
                vname = f"nf{i}"
                filter_lines.append(f"FILTER v.`{key}` == @{vname}")
                bind_vars[vname] = val

        filters_str = ""
        if filter_lines:
            filters_str = "\n  " + "\n  ".join(filter_lines)

        return_expr = "DISTINCT v" if deduplicate else "v"

        aql = (
            f"FOR v IN @depthVal..@depthVal {dir_str} @start {graph_source}"
            f"{filters_str}\n"
            f"  LIMIT @lim\n"
            f"  RETURN {return_expr}"
        )

        logger.info(f"GraphTraversalAgent: Neighbors AQL: {aql[:200]}...")
        cursor = db.aql.execute(aql, bind_vars=bind_vars, count=True)
        results = list(cursor)

        return {
            "results": results,
            "count": len(results),
            "aql_generated": aql,
        }
