import logging
from typing import Any, Dict, Optional

from arango.exceptions import (
    DatabaseCreateError,
    DatabaseDeleteError,
    DatabaseListError,
)

from agents.agent_base import SYSTEM_DB, ArangoAgentBase, handle_arango_errors
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class DatabaseManagementAgent(ArangoAgentBase):
    """Agent for ArangoDB database management operations (create, list, delete, info)."""

    @handle_arango_errors(
        "DatabaseManagementAgent",
        "Database",
        specific_exceptions=(DatabaseListError, DatabaseCreateError, DatabaseDeleteError),
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation = mcp_tool_inputs.get("operation")
        db_name_param: Optional[str] = mcp_tool_inputs.get("database_name")

        system_db = arango_connector.get_system_db()

        if operation == "list_databases":
            databases = await self.run_sync(system_db.databases)
            return {"databases": databases}

        elif operation == "create_database":
            db_to_create_name = db_name_param
            if not db_to_create_name:
                return {"error": "Database name is required for creation."}
            if await self.run_sync(system_db.has_database, db_to_create_name):
                return {"status": f"Database '{db_to_create_name}' already exists."}

            success = await self.run_sync(system_db.create_database, name=db_to_create_name)
            return {"status": f"Database '{db_to_create_name}' created.", "success": success}

        elif operation == "delete_database":
            db_to_delete_name = db_name_param
            if not db_to_delete_name:
                return {"error": "Database name is required for deletion."}
            if not await self.run_sync(system_db.has_database, db_to_delete_name):
                return {"error": f"Database '{db_to_delete_name}' not found."}
            if db_to_delete_name == SYSTEM_DB:
                return {"error": "Cannot delete the _system database."}

            success = await self.run_sync(
                system_db.delete_database, db_to_delete_name, ignore_missing=False
            )
            return {"status": f"Database '{db_to_delete_name}' deleted.", "success": success}

        elif operation == "get_database_info":
            db_to_inspect, target_db_name = self.resolve_db(db_name_param)
            info = await self.run_sync(db_to_inspect.properties)
            return {"database_info": info, "database_name": target_db_name}

        else:
            return {"error": f"Unknown database operation: {operation}"}
