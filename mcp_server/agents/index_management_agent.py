import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import (ArangoServerError, IndexCreateError,
                               IndexDeleteError, IndexListError)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from ..arango_connector import arango_connector
from ..config import settings
from .agent_base import ArangoAgentBase

logger = logging.getLogger(__name__)


class IndexManagementAgent(ArangoAgentBase):
    def _initialize_llm(self) -> BaseChatModel:
        return ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=self.api_key,
            convert_system_message_to_human=True,
        )

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: str = (
            mcp_tool_inputs.get("database_name") or settings.arango.default_db_name
        )
        collection_name: Optional[str] = mcp_tool_inputs.get("collection_name")
        index_definition: Optional[Dict[str, Any]] = mcp_tool_inputs.get(
            "index_definition"
        )
        index_id_or_name: Optional[str] = mcp_tool_inputs.get("index_id_or_name")

        logger.info(
            f"IndexManagementAgent: Op='{operation}', DB='{database_name}', Collection='{collection_name}'"
        )

        if not collection_name:
            return {"error": "Collection name is required for index operations."}

        try:
            if not arango_connector.client:
                return {"error": "ArangoDB client not initialized."}

            db = arango_connector.client.db(
                database_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

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
                # Example validation LLM could do:
                # if index_definition.get("type") == "persistent" and not index_definition.get("fields"):
                #     return {"error": "Persistent index requires 'fields' to be specified."}
                index_info = collection.add_index(index_definition)
                return {
                    "status": "Index created successfully.",
                    "index_info": index_info,
                }

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
                        (idx for idx in indexes if idx.get("name") == index_id_or_name),
                        None,
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

        except (
            IndexListError,
            IndexCreateError,
            IndexDeleteError,
            ArangoServerError,
        ) as e:
            logger.error(f"IndexManagementAgent: ArangoDB error - {e}")
            return {
                "error": f"ArangoDB Index Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"IndexManagementAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}
