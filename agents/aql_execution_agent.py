import logging
from typing import Any, Dict

from arango.exceptions import AQLQueryExecuteError, ArangoServerError

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector
from config import settings

logger = logging.getLogger(__name__)


class AQLExecutionAgent(ArangoAgentBase):
    """Agent for executing AQL queries against ArangoDB."""

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        aql_query: str = mcp_tool_inputs.get("aql_query", "")
        bind_vars: Dict[str, Any] = mcp_tool_inputs.get("bind_vars", {})
        database_name: str = mcp_tool_inputs.get("database_name") or settings.arango.default_db_name

        if not aql_query:
            return {"error": "AQL query string cannot be empty."}

        logger.info(
            f"AQLExecutionAgent: Executing AQL in DB '{database_name}': {aql_query[:100]}... with bind_vars: {bind_vars}"
        )

        try:
            # Get the specific database if provided, else use default from connector
            if not arango_connector.client:
                logger.error("AQLExecutionAgent: ArangoDB client not initialized.")
                return {"error": "ArangoDB client not initialized."}

            db_to_query = arango_connector.client.db(
                database_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

            # Note: In production, consider adding query validation
            # to restrict dangerous operations (INSERT, UPDATE, REMOVE, REPLACE)
            # based on security requirements

            cursor = db_to_query.aql.execute(
                aql_query, bind_vars=bind_vars, count=True, full_count=True
            )
            results = [document for document in cursor]

            response = {
                "query_executed": aql_query,
                "bind_vars_used": bind_vars,
                "database_queried": database_name,
                "count": cursor.count(),  # Number of documents returned in the current batch (if paginated)
                "full_count": (
                    cursor.full_count() if hasattr(cursor, "full_count") else None
                ),  # Total documents matching (if applicable)
                "results": results,
                "extra_stats": cursor.statistics(),
            }
            logger.info(f"AQLExecutionAgent: Query successful, returned {len(results)} documents.")
            return response

        except AQLQueryExecuteError as e:
            logger.error(f"AQLExecutionAgent: AQL execution error in DB '{database_name}': {e}")
            return {
                "error": f"AQL Execution Error: {e.error_message}",
                "error_code": e.error_code,
                "details": str(e),
            }
        except ArangoServerError as e:  # Catch other server errors like DB not found
            logger.error(f"AQLExecutionAgent: ArangoServerError in DB '{database_name}': {e}")
            return {
                "error": f"ArangoDB Server Error: {e.error_message}",
                "error_code": e.error_code,
                "details": str(e),
            }
        except Exception as e:
            logger.error(
                f"AQLExecutionAgent: Unexpected error during AQL execution in DB '{database_name}': {e}",
                exc_info=True,
            )
            return {"error": f"An unexpected error occurred: {str(e)}"}
