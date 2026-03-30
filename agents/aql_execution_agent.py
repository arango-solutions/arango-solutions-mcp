import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import (
    AQLQueryExecuteError,
    AQLQueryExplainError,
    AQLQueryValidateError,
    ArangoServerError,
)

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class AQLExecutionAgent(ArangoAgentBase):
    """Agent for executing, explaining, and validating AQL queries."""

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "execute")
        aql_query: str = mcp_tool_inputs.get("aql_query", "")
        bind_vars: Dict[str, Any] = mcp_tool_inputs.get("bind_vars", {})
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")

        if not aql_query:
            return {"error": "AQL query string cannot be empty."}

        if operation == "explain":
            return await self._explain(aql_query, bind_vars, database_name, mcp_tool_inputs)
        elif operation == "validate":
            return await self._validate(aql_query, database_name)

        # Default: execute

        logger.info(
            f"AQLExecutionAgent: Executing AQL in DB '{database_name}': "
            f"{aql_query[:100]}... bind_vars_keys={list(bind_vars.keys()) if bind_vars else []}"
        )

        try:
            db_to_query = arango_connector.get_db(database_name)
            database_name = database_name or db_to_query.name

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

    async def _explain(
        self,
        aql_query: str,
        bind_vars: Dict[str, Any],
        database_name: Optional[str],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        all_plans: bool = inputs.get("all_plans", False)
        max_plans: Optional[int] = inputs.get("max_plans")
        opt_rules: Optional[List[str]] = inputs.get("opt_rules")

        logger.info(
            f"AQLExecutionAgent: Explaining AQL in DB '{database_name}': {aql_query[:100]}..."
        )

        try:
            db = arango_connector.get_db(database_name)

            kwargs: Dict[str, Any] = {"all_plans": all_plans}
            if bind_vars:
                kwargs["bind_vars"] = bind_vars
            if max_plans is not None:
                kwargs["max_plans"] = max_plans
            if opt_rules is not None:
                kwargs["opt_rules"] = opt_rules

            plan = db.aql.explain(aql_query, **kwargs)

            return {
                "query": aql_query,
                "plan": plan,
            }

        except AQLQueryExplainError as e:
            logger.error(f"AQLExecutionAgent: Explain error - {e}")
            return {
                "error": f"AQL Explain Error: {e.error_message}",
                "error_code": e.error_code,
            }
        except Exception as e:
            logger.error(f"AQLExecutionAgent: Explain unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}

    async def _validate(self, aql_query: str, database_name: Optional[str]) -> Dict[str, Any]:
        logger.info(
            f"AQLExecutionAgent: Validating AQL in DB '{database_name}': {aql_query[:100]}..."
        )

        try:
            db = arango_connector.get_db(database_name)
            result = db.aql.validate(aql_query)

            return {
                "query": aql_query,
                "valid": True,
                "parse_result": result,
            }

        except AQLQueryValidateError as e:
            logger.error(f"AQLExecutionAgent: Validate error - {e}")
            return {
                "query": aql_query,
                "valid": False,
                "error": f"AQL Validation Error: {e.error_message}",
                "error_code": e.error_code,
            }
        except Exception as e:
            logger.error(f"AQLExecutionAgent: Validate unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}
