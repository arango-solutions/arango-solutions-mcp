# mcp_server/agents/database_management_agent.py
import logging
from typing import Any, Dict, List

from arango.exceptions import (
    DatabaseCreateError,
    DatabaseDeleteError,
    DatabaseListError,
    ArangoServerError
)

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector # arango_connector.get_db() returns StandardDatabase
from config import settings


logger = logging.getLogger(__name__)

class DatabaseManagementAgent(ArangoAgentBase):
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation = mcp_tool_inputs.get("operation")
        db_name_param = mcp_tool_inputs.get("database_name") # Parameter from tool call

        try:
            # For listing databases, creating, or deleting, we always need the _system db context
            if not arango_connector.client:
                logger.error("DatabaseManagementAgent: ArangoDB client not initialized.")
                return {"error": "ArangoDB client not initialized."}

            # Get a connection to the _system database for system-level operations
            system_db = arango_connector.client.db(
                "_system",
                username=settings.arango.root_username,
                password=settings.arango.root_password
            )

            if operation == "list_databases":
                databases = system_db.databases() # Correct: called on _system db
                return {"databases": databases}
            
            elif operation == "create_database":
                db_to_create_name = db_name_param # Use the name passed for creation
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
                if db_to_delete_name == "_system": # This check is also in the tool, but good to have defense in depth
                    return {"error": "Cannot delete the _system database."}
                
                success = system_db.delete_database(db_to_delete_name, ignore_missing=False)
                return {"status": f"Database '{db_to_delete_name}' deleted.", "success": success}
            
            elif operation == "get_database_info":
                # For get_database_info, we connect to the specific database requested, or default
                target_db_name = db_name_param or settings.arango.default_db_name
                
                if not arango_connector.client: # Should be caught above, but for safety
                    return {"error": "ArangoDB client not initialized."}

                db_to_inspect = arango_connector.client.db(
                    target_db_name,
                    username=settings.arango.root_username,
                    password=settings.arango.root_password
                )
                info = db_to_inspect.properties() 
                return {"database_info": info, "database_name": target_db_name}
            
            else:
                return {"error": f"Unknown database operation: {operation}"}
                
        except (DatabaseListError, DatabaseCreateError, DatabaseDeleteError, ArangoServerError) as e:
            logger.error(f"ArangoDB database operation error (Op: {operation}, DB Param: {db_name_param}): {e}")
            return {"error": f"ArangoDB Error: {e.error_message if hasattr(e, 'error_message') else str(e)}", "error_code": e.error_code if hasattr(e, 'error_code') else None}
        except Exception as e:
            logger.exception(f"Unexpected error in DatabaseManagementAgent (Op: {operation}, DB Param: {db_name_param}):")
            return {"error": f"Unexpected error: {str(e)}"}