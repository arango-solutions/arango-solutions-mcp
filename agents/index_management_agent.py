import logging
from typing import Any, Dict, Optional

from arango.exceptions import IndexCreateError, IndexDeleteError, IndexListError

from agents.agent_base import ArangoAgentBase, handle_arango_errors
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class IndexManagementAgent(ArangoAgentBase):
    """Agent for managing ArangoDB indexes."""

    @handle_arango_errors(
        "IndexManagementAgent",
        "ArangoDB Index",
        (IndexListError, IndexCreateError, IndexDeleteError),
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")
        collection_name: Optional[str] = mcp_tool_inputs.get("collection_name")
        index_definition: Optional[Dict[str, Any]] = mcp_tool_inputs.get("index_definition")
        index_id_or_name: Optional[str] = mcp_tool_inputs.get("index_id_or_name")

        logger.info(
            f"IndexManagementAgent: Op='{operation}', DB='{database_name}', Collection='{collection_name}'"
        )

        if not collection_name:
            return {"error": "Collection name is required for index operations."}

        db = arango_connector.get_db(database_name)
        database_name = database_name or db.name

        if not db.has_collection(collection_name):
            return {
                "error": f"Collection '{collection_name}' not found in database '{database_name}'."
            }

        collection = db.collection(collection_name)

        if operation == "list_indexes":
            indexes = collection.indexes()
            return {"indexes": indexes}

        elif operation == "create_index":
            if not index_definition:
                return {"error": "Index definition is required for creation."}
            if not index_definition.get("type"):
                return {"error": "Index definition must include 'type' field."}

            index_type = index_definition["type"]
            fields = index_definition.get("fields", [])

            supported_types = {
                "persistent",
                "inverted",
                "geo",
                "ttl",
                "fulltext",
                "mdi",
                "mdi-prefixed",
                "vector",
            }
            if index_type not in supported_types:
                return {
                    "error": f"Unsupported index type: {index_type}. "
                    f"Supported: {', '.join(sorted(supported_types))}"
                }

            if not fields:
                return {"error": f"{index_type.capitalize()} index requires 'fields'."}

            # Use the unified add_index() API (python-arango 8.x+).
            # Pass the definition dict directly — the server validates the shape.
            index_data = dict(index_definition)
            index_data["fields"] = fields
            index_info = collection.add_index(index_data)

            return {"status": "Index created successfully.", "index_info": index_info}

        elif operation == "delete_index":
            if not index_id_or_name:
                return {"error": "Index ID or name is required for deletion."}

            # Primary index cannot be deleted. Check if it's the primary index.
            indexes = collection.indexes()
            primary_index_id = next(
                (idx["id"] for idx in indexes if idx["type"] == "primary"), None
            )
            target_index_id = index_id_or_name
            if index_id_or_name not in [
                idx["id"] for idx in indexes
            ]:  # if name is given, try to find id
                target_index_obj = next(
                    (idx for idx in indexes if idx.get("name") == index_id_or_name), None
                )
                if target_index_obj:
                    target_index_id = target_index_obj["id"]
                else:  # not found by id or name
                    return {
                        "error": f"Index '{index_id_or_name}' not found in collection '{collection_name}'."
                    }

            if primary_index_id and target_index_id == primary_index_id:
                return {"error": "The primary index cannot be deleted."}

            success = collection.delete_index(
                target_index_id, ignore_missing=False
            )  # already checked existence
            return {
                "status": f"Index '{index_id_or_name}' deleted successfully.",
                "success": success,
            }

        else:
            return {"error": f"Unknown index operation: {operation}"}
