import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import (
    ArangoServerError,
    DocumentDeleteError,
    DocumentGetError,
    DocumentInsertError,
    DocumentReplaceError,
    DocumentUpdateError,
)

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector
from config import settings

logger = logging.getLogger(__name__)


class DocumentCRUDAgent(ArangoAgentBase):
    """Agent for document CRUD operations."""

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: str = mcp_tool_inputs.get("database_name") or settings.arango.default_db_name
        collection_name: Optional[str] = mcp_tool_inputs.get("collection_name")

        document_data: Optional[Dict[str, Any]] = mcp_tool_inputs.get("document_data")
        documents_data: Optional[List[Dict[str, Any]]] = mcp_tool_inputs.get("documents_data")
        document_key_or_id: Optional[str] = mcp_tool_inputs.get("document_key_or_id")

        filters: Optional[Dict[str, Any]] = mcp_tool_inputs.get("filters")
        sort_by: Optional[str] = mcp_tool_inputs.get("sort_by")
        sort_order: str = mcp_tool_inputs.get("sort_order", "ASC").upper()
        limit: int = mcp_tool_inputs.get("limit", 100)
        skip: int = mcp_tool_inputs.get("skip", 0)

        logger.info(
            f"DocumentCRUDAgent: Op='{operation}', DB='{database_name}', Collection='{collection_name}'"
        )

        # Collection name is required for all document operations
        if not collection_name:
            return {"error": "Collection name is required for document operations."}

        try:
            if not arango_connector.client:
                return {"error": "ArangoDB client not initialized."}

            db = arango_connector.client.db(
                database_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

            # Check if collection exists, create it if needed for insert operations
            if not db.has_collection(collection_name):
                if operation in ["create_document", "create_documents_bulk"]:
                    # Auto-create collection for insert operations
                    logger.info(f"Creating collection '{collection_name}' in database '{database_name}'")
                    db.create_collection(collection_name)
                else:
                    return {
                        "error": f"Collection '{collection_name}' not found in database '{database_name}'."
                    }

            collection = db.collection(collection_name)

            if operation == "create_document":
                if not document_data:
                    return {"error": "Document data is required."}
                meta = collection.insert(document_data)
                return {"status": "Document created successfully.", "metadata": meta}

            elif operation == "create_documents_bulk":
                if not documents_data:
                    return {"error": "A list of documents data is required."}
                results = collection.insert_many(documents_data)
                return {"status": "Bulk document insertion attempted.", "results": results}

            elif operation == "read_document":
                if not document_key_or_id:
                    return {"error": "Document key/ID is required."}
                doc = collection.get(document_key_or_id)
                return {"document": doc} if doc else {"error": "Document not found."}

            elif operation == "read_documents_filter":
                if not filters:
                    return {"error": "Filters are required."}

                sort_options = None
                if sort_by:
                    sort_options = [{"field": sort_by, "direction": sort_order.lower()}]

                cursor = collection.find(filters, skip=skip, limit=limit)
                docs = [doc for doc in cursor]

                return {
                    "documents": docs,
                    "count": len(docs),
                    "note": "For sorting, please use the execute_aql tool.",
                }

            elif operation == "update_document":
                if not document_data:
                    return {"error": "Document data is required."}
                if not ("_key" in document_data or "_id" in document_data):
                    return {"error": "Document data must include _key or _id field."}
                meta = collection.update(document_data, merge=True)
                return {"status": "Document updated successfully.", "metadata": meta}

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
