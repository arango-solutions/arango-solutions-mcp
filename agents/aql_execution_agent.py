import logging
from typing import Any, Dict, List

from arango.exceptions import (
    AQLQueryExecuteError,
    AQLQueryExplainError,
    AQLQueryValidateError,
)

from agents.agent_base import ArangoAgentBase, handle_arango_errors
from config import settings

logger = logging.getLogger(__name__)


class AQLExecutionAgent(ArangoAgentBase):
    """Agent for executing, explaining, and validating AQL queries."""

    @handle_arango_errors("AQLExecutionAgent", "AQL", specific_exceptions=(AQLQueryExecuteError,))
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "execute")
        aql_query: str = mcp_tool_inputs.get("aql_query", "")
        bind_vars: Dict[str, Any] = mcp_tool_inputs.get("bind_vars", {})
        database_name: str | None = mcp_tool_inputs.get("database_name")

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

        db_to_query, database_name = self.resolve_db(database_name)

        configured_max_runtime = mcp_tool_inputs.get("max_runtime")
        if configured_max_runtime is None:
            configured_max_runtime = settings.server.default_aql_max_runtime

        execute_kwargs: Dict[str, Any] = dict(
            bind_vars=bind_vars, count=True, full_count=True
        )
        if configured_max_runtime and configured_max_runtime > 0:
            execute_kwargs["max_runtime"] = float(configured_max_runtime)

        cursor = await self.run_sync(
            db_to_query.aql.execute, aql_query, **execute_kwargs
        )
        results = list(cursor)

        response = {
            "query_executed": aql_query,
            "database_queried": database_name,
            "max_runtime": (
                configured_max_runtime
                if configured_max_runtime and configured_max_runtime > 0
                else None
            ),
            "count": cursor.count(),
            "full_count": (
                cursor.full_count() if hasattr(cursor, "full_count") else None
            ),
            "results": results,
            "extra_stats": cursor.statistics(),
        }
        logger.info(f"AQLExecutionAgent: Query successful, returned {len(results)} documents.")
        return response

    async def _explain(
        self,
        aql_query: str,
        bind_vars: Dict[str, Any],
        database_name: str | None,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        all_plans: bool = inputs.get("all_plans", False)
        max_plans: int | None = inputs.get("max_plans")
        opt_rules: List[str] | None = inputs.get("opt_rules")

        logger.info(
            f"AQLExecutionAgent: Explaining AQL in DB '{database_name}': {aql_query[:100]}..."
        )

        try:
            db, _ = self.resolve_db(database_name)

            kwargs: Dict[str, Any] = {"all_plans": all_plans}
            if bind_vars:
                kwargs["bind_vars"] = bind_vars
            if max_plans is not None:
                kwargs["max_plans"] = max_plans
            if opt_rules is not None:
                kwargs["opt_rules"] = opt_rules

            plan = await self.run_sync(db.aql.explain, aql_query, **kwargs)

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

    async def _validate(self, aql_query: str, database_name: str | None) -> Dict[str, Any]:
        logger.info(
            f"AQLExecutionAgent: Validating AQL in DB '{database_name}': {aql_query[:100]}..."
        )

        try:
            db, _ = self.resolve_db(database_name)
            result = await self.run_sync(db.aql.validate, aql_query)

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
