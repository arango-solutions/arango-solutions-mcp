import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import (ArangoServerError, DocumentDeleteError,
                               DocumentGetError, DocumentInsertError,
                               DocumentReplaceError, DocumentUpdateError)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from ..arango_connector import arango_connector
from ..config import settings
from .agent_base import ArangoAgentBase

logger = logging.getLogger(__name__)


class DocumentCRUDAgent(ArangoAgentBase):
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

        document_data: Optional[Dict[str, Any]] = mcp_tool_inputs.get("document_data")
        documents_data: Optional[List[Dict[str, Any]]] = mcp_tool_inputs.get(
            "documents_data"
        )
        document_key_or_id: Optional[str] = mcp_tool_inputs.get("document_key_or_id")

        # For query/read_documents_filter
        filters: Optional[Dict[str, Any]] = mcp_tool_inputs.get("filters")
        sort_by: Optional[str] = mcp_tool_inputs.get("sort_by")
        sort_order: str = mcp_tool_inputs.get("sort_order", "ASC").upper()
        limit: int = mcp_tool_inputs.get("limit", 100)
        skip: int = mcp_tool_inputs.get("skip", 0)

        logger.info(
            f"DocumentCRUDAgent: Op='{operation}', DB='{database_name}', Collection='{collection_name}'"
        )

        if (
            not collection_name and operation not in []
        ):  # Some ops might not need collection_name initially
            return {
                "error": "Collection name is required for most document operations."
            }

        try:
            if not arango_connector.client:
                return {"error": "ArangoDB client not initialized."}

            db = arango_connector.client.db(
                database_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

            if not db.has_collection(collection_name) and collection_name:
                return {
                    "error": f"Collection '{collection_name}' not found in database '{database_name}'."
                }

            collection = db.collection(collection_name) if collection_name else None

            if operation == "create_document":
                if not collection or not document_data:
                    return {"error": "Collection name and document data are required."}
                meta = collection.insert(document_data)
                return {"status": "Document created successfully.", "metadata": meta}

            elif operation == "create_documents_bulk":
                if not collection or not documents_data:
                    return {
                        "error": "Collection name and a list of documents data are required."
                    }
                results = collection.insert_many(documents_data)
                # results can be a mix of metadata and error dicts
                return {
                    "status": "Bulk document insertion attempted.",
                    "results": results,
                }

            elif operation == "read_document":
                if not collection or not document_key_or_id:
                    return {
                        "error": "Collection name and document key/ID are required."
                    }
                doc = collection.get(document_key_or_id)
                return {"document": doc} if doc else {"error": "Document not found."}

            elif operation == "read_documents_filter":  # Simplified find
                if not collection or not filters:
                    return {"error": "Collection name and filters are required."}

                sort_options = None
                if sort_by:
                    sort_options = [{"field": sort_by, "direction": sort_order.lower()}]

                # python-arango's find doesn't directly take sort like this.
                # AQL is better for complex queries. For simple find with sort, we'd build AQL.
                # For PoC, we'll use find and then sort in Python if needed, or recommend AQL tool.
                # Using collection.find which supports basic filtering. Sorting is not directly supported.
                # For sorting, AQL is the way to go.
                # cursor = collection.find(filters, skip=skip, limit=limit, sort=sort_options) # sort is not a param for collection.find

                # Basic find, no sort via simple API. User should use AQL for sorting.
                cursor = collection.find(filters, skip=skip, limit=limit)
                docs = [doc for doc in cursor]
                # if sort_by:
                #     docs.sort(key=lambda x: x.get(sort_by), reverse=(sort_order == "DESC"))

                return {
                    "documents": docs,
                    "count": len(docs),
                    "note": "For sorting, please use the execute_aql tool.",
                }

            elif operation == "update_document":
                if (
                    not collection
                    or not document_data
                    or not ("_key" in document_data or "_id" in document_data)
                ):
                    return {
                        "error": "Collection name and document data (with _key or _id) are required."
                    }
                meta = collection.update(
                    document_data, merge=True
                )  # merge=True for partial update
                return {"status": "Document updated successfully.", "metadata": meta}

            # TODO: Implement update_documents_bulk, delete_document, delete_documents_bulk, replace_document, upsert_document

            else:
                return {"error": f"Unknown document operation: {operation}"}

        except (
            DocumentInsertError,
            DocumentGetError,
            DocumentUpdateError,
            DocumentDeleteError,
            DocumentReplaceError,
            ArangoServerError,
        ) as e:
            logger.error(f"DocumentCRUDAgent: ArangoDB error - {e}")
            return {
                "error": f"ArangoDB Document Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"DocumentCRUDAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}
