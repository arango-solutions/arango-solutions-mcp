from typing import Any, Dict, Literal, Optional

from pydantic import Field

from agents.cluster_management_agent import ClusterManagementAgent
from server import mcp_app

cluster_agent = ClusterManagementAgent()


@mcp_app.tool(
    name="cluster-health",
    description="""Returns the health status of all servers in an ArangoDB cluster.

    Reports per-server information including:
    - Server ID and short name
    - Role (Coordinator, DBServer, Agent)
    - Status (GOOD, BAD, FAILED)
    - Host, port, and engine details
    - Leader/follower status

    Use this to:
    - Monitor cluster availability
    - Detect failed or degraded servers
    - Verify cluster topology
    - Troubleshoot connectivity issues

    Returns an error on single-server deployments.
    """,
)
async def cluster_health(
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await cluster_agent.arun({"operation": "cluster_health", "database_name": database_name})


@mcp_app.tool(
    name="cluster-server-role",
    description="""Returns the role of the server handling this request.

    Possible roles:
    - SINGLE: standalone single-server deployment
    - COORDINATOR: cluster coordinator (handles client requests)
    - PRIMARY / DBSERVER: cluster DB server (stores data)
    - AGENT: cluster agent (manages consensus)
    - UNDEFINED: role could not be determined

    Useful for confirming whether you're connected to a cluster or
    single-server instance.
    """,
)
async def cluster_server_role(
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await cluster_agent.arun(
        {"operation": "cluster_server_role", "database_name": database_name}
    )


@mcp_app.tool(
    name="cluster-server-count",
    description="""Returns the number of coordinator and DB servers in the cluster.

    Useful for capacity planning and verifying expected cluster size.
    Returns an error on single-server deployments.
    """,
)
async def cluster_server_count(
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await cluster_agent.arun(
        {"operation": "cluster_server_count", "database_name": database_name}
    )


@mcp_app.tool(
    name="cluster-endpoints",
    description="""Lists all coordinator endpoints in the cluster.

    Returns URLs of all coordinators that can accept client connections.
    Useful for load balancing configuration and failover setup.
    """,
)
async def cluster_endpoints(
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await cluster_agent.arun(
        {"operation": "cluster_endpoints", "database_name": database_name}
    )


@mcp_app.tool(
    name="cluster-server-statistics",
    description="""Returns runtime statistics for a specific cluster server.

    Includes CPU usage, memory, request counters, and other metrics.
    Requires the server_id which can be obtained from cluster-health.
    """,
)
async def cluster_server_statistics(
    server_id: str = Field(
        description="""The ID of the cluster server to query.
        Obtain from the cluster-health tool output (e.g., 'PRMR-abc12345').
        """
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await cluster_agent.arun(
        {
            "operation": "cluster_server_statistics",
            "server_id": server_id,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="cluster-calculate-imbalance",
    description="""Calculates shard distribution imbalance across cluster DB servers.

    Shows how evenly shards (leaders and followers) are distributed.
    A well-balanced cluster has roughly equal shard counts per server.
    Use this before deciding whether to run a rebalance operation.

    Returns metrics including:
    - Leader and follower distribution per server
    - Total shard counts
    - Imbalance scores
    """,
)
async def cluster_calculate_imbalance(
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await cluster_agent.arun(
        {"operation": "cluster_calculate_imbalance", "database_name": database_name}
    )


@mcp_app.tool(
    name="cluster-rebalance",
    description="""Triggers automatic shard rebalancing across cluster DB servers.

    Redistributes shard leaders and followers to achieve better balance.
    This can improve query performance and resource utilization.

    WARNING: Rebalancing moves data between servers and can impact
    performance during the operation. Run during low-traffic periods.

    The operation is non-blocking — it initiates the rebalance and returns.
    Monitor progress with cluster-health and cluster-calculate-imbalance.
    """,
)
async def cluster_rebalance(
    max_moves: Optional[int] = Field(
        default=None,
        description="Maximum number of shard moves to perform. "
        "Lower values = safer but slower convergence.",
    ),
    move_leaders: Optional[bool] = Field(
        default=None, description="Whether to move leader shards. Default: true."
    ),
    move_followers: Optional[bool] = Field(
        default=None, description="Whether to move follower shards. Default: true."
    ),
    leader_changes: Optional[bool] = Field(
        default=None,
        description="Whether to change shard leadership. Default: true.",
    ),
    pi_factor: Optional[float] = Field(
        default=None,
        description="Weight factor for leader imbalance vs follower imbalance. "
        "Higher values prioritize leader balance. Default: 256.0.",
    ),
    exclude_system_collections: Optional[bool] = Field(
        default=None,
        description="Exclude system collections from rebalancing. Default: false.",
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "operation": "cluster_rebalance",
        "database_name": database_name,
    }
    if max_moves is not None:
        payload["max_moves"] = max_moves
    if move_leaders is not None:
        payload["move_leaders"] = move_leaders
    if move_followers is not None:
        payload["move_followers"] = move_followers
    if leader_changes is not None:
        payload["leader_changes"] = leader_changes
    if pi_factor is not None:
        payload["pi_factor"] = pi_factor
    if exclude_system_collections is not None:
        payload["exclude_system_collections"] = exclude_system_collections
    return await cluster_agent.arun(payload)


@mcp_app.tool(
    name="cluster-toggle-maintenance",
    description="""Toggles cluster-wide maintenance mode on or off.

    Maintenance mode pauses automatic shard rebalancing and failover.
    Use when performing planned maintenance, upgrades, or diagnostics.

    WARNING: While in maintenance mode, the cluster will NOT
    automatically recover from server failures. Only enable when needed
    and remember to disable after maintenance is complete.
    """,
)
async def cluster_toggle_maintenance(
    mode: Literal["on", "off"] = Field(
        description="'on' to enable maintenance mode, 'off' to disable it."
    ),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await cluster_agent.arun(
        {
            "operation": "cluster_toggle_maintenance",
            "mode": mode,
            "database_name": database_name,
        }
    )


@mcp_app.tool(
    name="collection-shard-distribution",
    description="""Returns shard distribution details for a specific collection.

    Shows how a collection's data is distributed across cluster servers:
    - Number of shards
    - Shard keys used for distribution
    - Replication factor and write concern
    - Sharding strategy
    - Whether it's a SmartGraph collection

    On single-server deployments, returns the collection's sharding
    configuration metadata (which is stored but not actively used).
    """,
)
async def collection_shard_distribution(
    collection_name: str = Field(description="Name of the collection to inspect."),
    database_name: Optional[str] = Field(
        default=None, description="Target database name. Uses default if not specified."
    ),
) -> Dict[str, Any]:
    return await cluster_agent.arun(
        {
            "operation": "collection_shard_distribution",
            "collection_name": collection_name,
            "database_name": database_name,
        }
    )
