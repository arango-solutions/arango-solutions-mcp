import logging
from typing import Any, Dict, Optional

from arango.exceptions import (
    ArangoServerError,
    DatabaseCreateError,
    DatabaseDeleteError,
    DatabaseListError,
)

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class DatabaseManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB database management operations (create, list, delete, info)."""

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation = mcp_tool_inputs.get("operation")
        db_name_param: Optional[str] = mcp_tool_inputs.get("database_name")

        try:
            system_db = arango_connector.get_system_db()

            if operation == "list_databases":
                databases = system_db.databases()  # Correct: called on _system db
                return {"databases": databases}

            elif operation == "create_database":
                db_to_create_name = db_name_param  # Use the name passed for creation
                if not db_to_create_name:
                    return {"error": "Database name is required for creation."}
                if system_db.has_database(db_to_create_name):
                    return {"status": f"Database '{db_to_create_name}' already exists."}

                success = system_db.create_database(name=db_to_create_name)
                return {"status": f"Database '{db_to_create_name}' created.", "success": success}

            elif operation == "delete_database":
                db_to_delete_name = db_name_param
                if not db_to_delete_name:
                    return {"error": "Database name is required for deletion."}
                if not system_db.has_database(db_to_delete_name):
                    return {"error": f"Database '{db_to_delete_name}' not found."}
                if (
                    db_to_delete_name == "_system"
                ):  # This check is also in the tool, but good to have defense in depth
                    return {"error": "Cannot delete the _system database."}

                success = system_db.delete_database(db_to_delete_name, ignore_missing=False)
                return {"status": f"Database '{db_to_delete_name}' deleted.", "success": success}

            elif operation == "get_database_info":
                db_to_inspect = arango_connector.get_db(db_name_param)
                target_db_name = db_name_param or db_to_inspect.name
                info = db_to_inspect.properties()
                return {"database_info": info, "database_name": target_db_name}

            else:
                return {"error": f"Unknown database operation: {operation}"}

        except (
            DatabaseListError,
            DatabaseCreateError,
            DatabaseDeleteError,
            ArangoServerError,
        ) as e:
            logger.error(
                f"ArangoDB database operation error (Op: {operation}, DB Param: {db_name_param}): {e}"
            )
            return {
                "error": f"ArangoDB Error: {e.error_message if hasattr(e, 'error_message') else str(e)}",
                "error_code": e.error_code if hasattr(e, "error_code") else None,
            }
        except Exception as e:
            logger.exception(
                f"Unexpected error in DatabaseManagementAgent (Op: {operation}, DB Param: {db_name_param}):"
            )
            return {"error": f"Unexpected error: {str(e)}"}
