import logging
from typing import Any, Dict, Optional

from arango.exceptions import (ArangoServerError, CollectionConfigureError,
                               CollectionCreateError, CollectionDeleteError,
                               CollectionListError, CollectionPropertiesError)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from ..arango_connector import arango_connector
from ..config import settings
from .agent_base import ArangoAgentBase

logger = logging.getLogger(__name__)


class CollectionManagementAgent(ArangoAgentBase):
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
        collection_type: str = mcp_tool_inputs.get(
            "collection_type", "document"
        )  # document, edge

        logger.info(
            f"CollectionManagementAgent: Op='{operation}', DB='{database_name}', Collection='{collection_name}'"
        )

        try:
            if not arango_connector.client:
                logger.error(
                    "CollectionManagementAgent: ArangoDB client not initialized."
                )
                return {"error": "ArangoDB client not initialized."}

            db = arango_connector.client.db(
                database_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

            if operation == "list_collections":
                all_collections_info = db.collections()
                # Filter out system collections (those starting with '_')
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
                return {
                    "database_name": database_name,
                    "collections": user_collections_info,
                }

            if (
                operation
                in [
                    "create_collection",
                    "delete_collection",
                    "get_collection_properties",
                ]
                and not collection_name
            ):
                return {
                    "error": f"Collection name is required for operation '{operation}'."
                }

            if operation == "create_collection":
                if db.has_collection(collection_name):  # type: ignore
                    return {
                        "status": f"Collection '{collection_name}' already exists in database '{database_name}'."
                    }

                is_edge = collection_type.lower() == "edge"
                created_collection = db.create_collection(collection_name, edge=is_edge)  # type: ignore
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

        except (
            CollectionListError,
            CollectionCreateError,
            CollectionDeleteError,
            CollectionPropertiesError,
            CollectionConfigureError,
            ArangoServerError,
        ) as e:
            logger.error(
                f"CollectionManagementAgent: ArangoDB error in DB '{database_name}', Collection '{collection_name}' - Op '{operation}': {e}"
            )
            return {
                "error": f"ArangoDB Collection Error: {e.error_message if hasattr(e, 'error_message') else str(e)}",
                "error_code": e.error_code if hasattr(e, "error_code") else None,
            }
        except Exception as e:
            logger.error(
                f"CollectionManagementAgent: Unexpected error in DB '{database_name}', Collection '{collection_name}' - Op '{operation}': {e}",
                exc_info=True,
            )
            return {"error": f"An unexpected error occurred: {str(e)}"}
