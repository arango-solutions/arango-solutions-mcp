import logging
from typing import Any, Dict, List, Optional, Union

from arango.exceptions import (
    CollectionConfigureError,
    CollectionCreateError,
    CollectionDeleteError,
    CollectionListError,
    CollectionPropertiesError,
)

from agents.agent_base import ArangoAgentBase, handle_arango_errors
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class CollectionManagementAgent(ArangoAgentBase):
    """Agent for managing ArangoDB collections."""

    @handle_arango_errors(
        "CollectionManagementAgent",
        "ArangoDB Collection",
        (
            CollectionListError,
            CollectionCreateError,
            CollectionDeleteError,
            CollectionPropertiesError,
            CollectionConfigureError,
        ),
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")
        collection_name: Optional[str] = mcp_tool_inputs.get("collection_name")
        collection_type: str = mcp_tool_inputs.get("collection_type", "document")

        # Sharding / cluster parameters
        number_of_shards: Optional[int] = mcp_tool_inputs.get("number_of_shards")
        shard_keys: Optional[List[str]] = mcp_tool_inputs.get("shard_keys")
        replication_factor: Optional[Union[int, str]] = mcp_tool_inputs.get("replication_factor")
        write_concern: Optional[int] = mcp_tool_inputs.get("write_concern")
        sharding_strategy: Optional[str] = mcp_tool_inputs.get("sharding_strategy")
        computed_values: Optional[List[Dict[str, Any]]] = mcp_tool_inputs.get("computed_values")

        logger.info(
            f"CollectionManagementAgent: Op='{operation}', DB='{database_name}', Collection='{collection_name}'"
        )

        db = arango_connector.get_db(database_name)
        database_name = database_name or db.name

        if operation == "list_collections":
            all_collections_info = db.collections()
            user_collections_info = [
                col_info
                for col_info in all_collections_info
                if not col_info.get("name", "").startswith("_")
            ]
            if not user_collections_info:
                return {
                    "database_name": database_name,
                    "collections": [],
                    "message": f"No user-defined collections found in database '{database_name}'.",
                }
            return {"database_name": database_name, "collections": user_collections_info}

        if (
            operation in ["create_collection", "delete_collection", "get_collection_properties"]
            and not collection_name
        ):
            return {"error": f"Collection name is required for operation '{operation}'."}

        if operation == "create_collection":
            if db.has_collection(collection_name):  # type: ignore
                return {
                    "status": f"Collection '{collection_name}' already exists in database '{database_name}'."
                }

            is_edge = collection_type.lower() == "edge"

            create_kwargs: Dict[str, Any] = {"edge": is_edge}
            # python-arango 8.x parameter names
            if number_of_shards is not None:
                create_kwargs["shard_count"] = number_of_shards
            if shard_keys is not None:
                create_kwargs["shard_fields"] = shard_keys
            if replication_factor is not None:
                create_kwargs["replication_factor"] = replication_factor
            if write_concern is not None:
                create_kwargs["write_concern"] = write_concern
            if sharding_strategy is not None:
                create_kwargs["sharding_strategy"] = sharding_strategy
            if computed_values is not None:
                create_kwargs["computedValues"] = computed_values

            created_collection = db.create_collection(collection_name, **create_kwargs)  # type: ignore
            return {
                "status": f"Collection '{collection_name}' (type: {'edge' if is_edge else 'document'}) created successfully in database '{database_name}'.",
                "collection_info": created_collection.properties(),
            }

        elif operation == "delete_collection":
            if not db.has_collection(collection_name):  # type: ignore
                return {
                    "error": f"Collection '{collection_name}' not found in database '{database_name}'."
                }

            db.delete_collection(collection_name, ignore_missing=False)  # type: ignore
            return {
                "status": f"Collection '{collection_name}' deleted successfully from database '{database_name}'."
            }

        elif operation == "get_collection_properties":
            if not db.has_collection(collection_name):  # type: ignore
                return {
                    "error": f"Collection '{collection_name}' not found in database '{database_name}'."
                }

            collection_obj = db.collection(collection_name)  # type: ignore
            properties = collection_obj.properties()
            count = collection_obj.count()
            statistics = collection_obj.statistics()
            revision = collection_obj.revision()
            return {
                "database_name": database_name,
                "collection_name": collection_name,
                "properties": properties,
                "document_count": count,
                "statistics": statistics,
                "revision_id": revision,
            }

        else:
            return {"error": f"Unknown collection operation: {operation}"}
