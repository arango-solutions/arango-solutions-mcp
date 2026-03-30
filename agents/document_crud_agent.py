import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import (
    DocumentDeleteError,
    DocumentGetError,
    DocumentInsertError,
    DocumentReplaceError,
    DocumentUpdateError,
)

from agents.agent_base import ArangoAgentBase, handle_arango_errors
from aql_utils import validate_aql_identifier
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class DocumentCRUDAgent(ArangoAgentBase):
    """Agent for document CRUD operations."""

    @handle_arango_errors(
        "DocumentCRUDAgent",
        "ArangoDB Document",
        (
            DocumentInsertError,
            DocumentGetError,
            DocumentUpdateError,
            DocumentDeleteError,
            DocumentReplaceError,
        ),
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")
        collection_name: Optional[str] = mcp_tool_inputs.get("collection_name")

        document_data: Optional[Dict[str, Any]] = mcp_tool_inputs.get("document_data")
        documents_data: Optional[List[Dict[str, Any]]] = mcp_tool_inputs.get("documents_data")
        document_key_or_id: Optional[str] = mcp_tool_inputs.get("document_key_or_id")

        filters: Optional[Dict[str, Any]] = mcp_tool_inputs.get("filters")
        limit: int = mcp_tool_inputs.get("limit", 100)
        skip: int = mcp_tool_inputs.get("skip", 0)

        logger.info(
            f"DocumentCRUDAgent: Op='{operation}', DB='{database_name}', Collection='{collection_name}'"
        )

        if not collection_name:
            return {"error": "Collection name is required for document operations."}

        db = arango_connector.get_db(database_name)
        database_name = database_name or db.name

        if not db.has_collection(collection_name):
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
                return {"error": "Document key or ID is required."}
            doc = collection.get(document_key_or_id)
            return {"document": doc} if doc else {"error": "Document not found."}

        elif operation == "read_documents_filter":
            if not filters:
                return {"error": "Filters are required."}
            cursor = collection.find(filters, skip=skip, limit=limit)
            docs = [doc for doc in cursor]
            return {
                "documents": docs,
                "count": len(docs),
                "note": "For sorting, use the execute-aql-query tool.",
            }

        elif operation == "update_document":
            if not document_data or not ("_key" in document_data or "_id" in document_data):
                return {"error": "Document data with _key or _id is required."}
            meta = collection.update(document_data, merge=True)
            return {"status": "Document updated successfully.", "metadata": meta}

        elif operation == "delete_document":
            if not document_key_or_id:
                return {"error": "Document key or ID is required."}
            meta = collection.delete(document_key_or_id, ignore_missing=False)
            return {"status": "Document deleted successfully.", "metadata": meta}

        elif operation == "replace_document":
            if not document_data or not ("_key" in document_data or "_id" in document_data):
                return {"error": "Complete document data with _key or _id is required."}
            meta = collection.replace(document_data)
            return {"status": "Document replaced successfully.", "metadata": meta}

        elif operation == "upsert_document":
            search_fields: Optional[Dict[str, Any]] = mcp_tool_inputs.get("search_fields")
            if not search_fields or not document_data:
                return {"error": "Both search_fields and document_data are required for upsert."}
            update_data = mcp_tool_inputs.get("update_data") or document_data

            validate_aql_identifier(collection_name, "collection_name")
            aql = (
                "UPSERT @search "
                "INSERT @insert "
                "UPDATE @update "
                "IN @@collection "
                "RETURN { old: OLD, new: NEW }"
            )
            cursor = db.aql.execute(
                aql,
                bind_vars={
                    "@collection": collection_name,
                    "search": search_fields,
                    "insert": document_data,
                    "update": update_data,
                },
            )
            result_doc = next(cursor, None)
            was_insert = result_doc["old"] is None if result_doc else None
            return {
                "status": "Document upserted successfully.",
                "was_insert": was_insert,
                "document": result_doc["new"] if result_doc else None,
            }

        elif operation == "update_documents_bulk":
            if not documents_data:
                return {"error": "A list of documents data is required."}
            results = collection.update_many(documents_data, merge=True)
            return {"status": "Bulk update attempted.", "results": results}

        elif operation == "delete_documents_bulk":
            if not documents_data:
                return {"error": "A list of documents (with _key or _id) is required."}
            results = collection.delete_many(documents_data)
            return {"status": "Bulk delete attempted.", "results": results}

        else:
            return {"error": f"Unknown document operation: {operation}"}
