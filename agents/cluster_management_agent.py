import logging
from typing import Any, Dict, Optional

from arango.exceptions import ArangoServerError

from agents.agent_base import ArangoAgentBase, handle_arango_errors

logger = logging.getLogger(__name__)


def _cluster_error_hint(exc: Exception) -> dict | None:
    """Rewrite ArangoDB errors that indicate a non-cluster deployment."""
    msg = getattr(exc, "error_message", None) or str(exc)
    msg_lower = msg.lower()
    if isinstance(exc, ArangoServerError) and any(
        phrase in msg_lower for phrase in ("not a cluster", "not running", "not supported")
    ):
        return {"error": f"This operation requires a cluster deployment: {msg}"}
    if "500 error" in msg_lower or "max retries" in msg_lower:
        return {"error": f"This operation is not available on this deployment: {exc}"}
    return None


class ClusterManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB cluster introspection and shard administration."""

    @handle_arango_errors(
        "ClusterManagementAgent",
        "ArangoDB Cluster",
        on_arango_error=_cluster_error_hint,
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")

        logger.info(f"ClusterManagementAgent: Op='{operation}', DB='{database_name}'")

        db, database_name = self.resolve_db(database_name)
        cluster = db.cluster

        if operation == "cluster_health":
            health = await self.run_sync(cluster.health)
            return {"health": health}

        elif operation == "cluster_server_role":
            role = await self.run_sync(cluster.server_role)
            return {"role": role}

        elif operation == "cluster_server_count":
            count = await self.run_sync(cluster.server_count)
            return {"server_count": count}

        elif operation == "cluster_endpoints":
            endpoints = await self.run_sync(cluster.endpoints)
            return {"endpoints": endpoints}

        elif operation == "cluster_server_id":
            sid = await self.run_sync(cluster.server_id)
            return {"server_id": sid}

        elif operation == "cluster_server_statistics":
            server_id: Optional[str] = mcp_tool_inputs.get("server_id")
            if not server_id:
                return {"error": "server_id is required for server statistics."}
            stats = await self.run_sync(cluster.server_statistics, server_id)
            return {"statistics": stats}

        elif operation == "cluster_server_engine":
            server_id = mcp_tool_inputs.get("server_id")
            if not server_id:
                return {"error": "server_id is required for server engine info."}
            engine = await self.run_sync(cluster.server_engine, server_id)
            return {"engine": engine}

        elif operation == "cluster_calculate_imbalance":
            imbalance = await self.run_sync(cluster.calculate_imbalance)
            return {"imbalance": imbalance}

        elif operation == "cluster_rebalance":
            kwargs: Dict[str, Any] = self.pack_optional(
                {},
                max_moves=mcp_tool_inputs.get("max_moves"),
                move_leaders=mcp_tool_inputs.get("move_leaders"),
                move_followers=mcp_tool_inputs.get("move_followers"),
                leader_changes=mcp_tool_inputs.get("leader_changes"),
                pi_factor=mcp_tool_inputs.get("pi_factor"),
                exclude_system_collections=mcp_tool_inputs.get("exclude_system_collections"),
            )

            result = await self.run_sync(cluster.rebalance, **kwargs)
            return {"rebalance_result": result}

        elif operation == "cluster_toggle_maintenance":
            mode: Optional[str] = mcp_tool_inputs.get("mode")
            if mode not in ("on", "off"):
                return {"error": "mode must be 'on' or 'off'."}
            result = await self.run_sync(cluster.toggle_maintenance_mode, mode)
            return {"maintenance": result}

        elif operation == "collection_shard_distribution":
            collection_name: Optional[str] = mcp_tool_inputs.get("collection_name")
            if not collection_name:
                return {"error": "collection_name is required for shard distribution."}
            col = await self.run_sync(db.collection, collection_name)
            props = await self.run_sync(col.properties)
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
