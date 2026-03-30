import logging
from typing import Any, Dict, Optional

from arango.exceptions import ArangoServerError

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class ClusterManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB cluster introspection and shard administration."""

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")

        logger.info(f"ClusterManagementAgent: Op='{operation}', DB='{database_name}'")

        try:
            db = arango_connector.get_db(database_name)
            database_name = database_name or db.name
            cluster = db.cluster

            if operation == "cluster_health":
                health = cluster.health()
                return {"health": health}

            elif operation == "cluster_server_role":
                role = cluster.server_role()
                return {"role": role}

            elif operation == "cluster_server_count":
                count = cluster.server_count()
                return {"server_count": count}

            elif operation == "cluster_endpoints":
                endpoints = cluster.endpoints()
                return {"endpoints": endpoints}

            elif operation == "cluster_server_id":
                sid = cluster.server_id()
                return {"server_id": sid}

            elif operation == "cluster_server_statistics":
                server_id: Optional[str] = mcp_tool_inputs.get("server_id")
                if not server_id:
                    return {"error": "server_id is required for server statistics."}
                stats = cluster.server_statistics(server_id)
                return {"statistics": stats}

            elif operation == "cluster_server_engine":
                server_id = mcp_tool_inputs.get("server_id")
                if not server_id:
                    return {"error": "server_id is required for server engine info."}
                engine = cluster.server_engine(server_id)
                return {"engine": engine}

            elif operation == "cluster_calculate_imbalance":
                imbalance = cluster.calculate_imbalance()
                return {"imbalance": imbalance}

            elif operation == "cluster_rebalance":
                max_moves: Optional[int] = mcp_tool_inputs.get("max_moves")
                move_leaders: Optional[bool] = mcp_tool_inputs.get("move_leaders")
                move_followers: Optional[bool] = mcp_tool_inputs.get("move_followers")
                leader_changes: Optional[bool] = mcp_tool_inputs.get("leader_changes")
                pi_factor: Optional[float] = mcp_tool_inputs.get("pi_factor")
                exclude_system: Optional[bool] = mcp_tool_inputs.get("exclude_system_collections")

                kwargs: Dict[str, Any] = {}
                if max_moves is not None:
                    kwargs["max_moves"] = max_moves
                if move_leaders is not None:
                    kwargs["move_leaders"] = move_leaders
                if move_followers is not None:
                    kwargs["move_followers"] = move_followers
                if leader_changes is not None:
                    kwargs["leader_changes"] = leader_changes
                if pi_factor is not None:
                    kwargs["pi_factor"] = pi_factor
                if exclude_system is not None:
                    kwargs["exclude_system_collections"] = exclude_system

                result = cluster.rebalance(**kwargs)
                return {"rebalance_result": result}

            elif operation == "cluster_toggle_maintenance":
                mode: Optional[str] = mcp_tool_inputs.get("mode")
                if mode not in ("on", "off"):
                    return {"error": "mode must be 'on' or 'off'."}
                result = cluster.toggle_maintenance_mode(mode)
                return {"maintenance": result}

            elif operation == "collection_shard_distribution":
                collection_name: Optional[str] = mcp_tool_inputs.get("collection_name")
                if not collection_name:
                    return {"error": "collection_name is required for shard distribution."}
                col = db.collection(collection_name)
                props = col.properties()
                shard_info = {
                    "collection": collection_name,
                    "numberOfShards": props.get("numberOfShards"),
                    "shardKeys": props.get("shardKeys"),
                    "replicationFactor": props.get("replicationFactor"),
                    "writeConcern": props.get("writeConcern"),
                    "shardingStrategy": props.get("shardingStrategy"),
                    "isSmart": props.get("isSmart", False),
                    "status": props.get("status"),
                }
                return {"shard_distribution": shard_info}

            else:
                return {"error": f"Unknown cluster operation: {operation}"}

        except ArangoServerError as e:
            error_msg = e.error_message if hasattr(e, "error_message") else str(e)
            lower_msg = str(error_msg).lower()
            if any(
                phrase in lower_msg for phrase in ("not a cluster", "not running", "not supported")
            ):
                return {"error": f"This operation requires a cluster deployment: {error_msg}"}
            logger.error(f"ClusterManagementAgent: ArangoDB error - {e}")
            return {"error": f"ArangoDB Cluster Error: {error_msg}"}
        except Exception as e:
            err_str = str(e).lower()
            if "500 error" in err_str or "max retries" in err_str:
                return {"error": f"This operation is not available on this deployment: {e}"}
            logger.error(f"ClusterManagementAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}
