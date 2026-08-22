import logging
import time
from typing import Any, Dict, List

from arango.exceptions import (
    AQLQueryExecuteError,
    AQLQueryExplainError,
    AQLQueryValidateError,
)

from arangodb_mcp.agents.agent_base import ArangoAgentBase, handle_arango_errors
from arangodb_mcp.config import settings
from arangodb_mcp.observability.metrics import observe_aql
from arangodb_mcp.policy.aql_classifier import AQLClassification, classify_aql_parse_result
from arangodb_mcp.policy.confirmation import ConfirmationError, consume_conditional_confirmation
from arangodb_mcp.policy.limits import effective_aql_runtime

logger = logging.getLogger(__name__)


def _aql_log_fragment(aql_query: str) -> str:
    """Return a log-safe representation of a user-supplied AQL query.

    By default this is structural metadata only — query length and a
    sha1 prefix to correlate log lines belonging to the same query
    without exposing literals. Set ``MCP_LOG_AQL_QUERIES=true`` (i.e.
    ``settings.server.log_aql_queries = True``) to log the first 100
    chars of the actual query for debugging.
    """
    import hashlib

    if settings.server.log_aql_queries:
        return f"{aql_query[:100]}..." if len(aql_query) > 100 else aql_query
    digest = hashlib.sha1(aql_query.encode("utf-8")).hexdigest()[:10]
    return f"<redacted len={len(aql_query)} sha1={digest}>"


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
            f"{_aql_log_fragment(aql_query)} "
            f"bind_vars_keys={list(bind_vars.keys()) if bind_vars else []}"
        )

        db_to_query, database_name = self.resolve_db(database_name)

        parse_result = await self.run_sync(db_to_query.aql.validate, aql_query)
        classification = classify_aql_parse_result(parse_result)
        if (
            settings.server.mcp_profile == "readonly"
            and classification.classification is not AQLClassification.READ
        ):
            return {
                "error": "Readonly AQL policy rejected a non-read or ambiguous query.",
                "error_code": "aql_policy_denied",
                "classification": classification.classification.value,
                "reasons": list(classification.reasons),
                "mutation_nodes": list(classification.mutation_nodes),
            }
        if classification.classification is AQLClassification.MUTATION:
            try:
                consume_conditional_confirmation()
            except ConfirmationError as exc:
                return {
                    "error": str(exc),
                    "error_code": exc.code,
                    "classification": classification.classification.value,
                    "mutation_nodes": list(classification.mutation_nodes),
                }

        configured_max_runtime = effective_aql_runtime(
            mcp_tool_inputs.get("max_runtime"),
            settings.server.default_aql_max_runtime,
        )

        execute_kwargs: Dict[str, Any] = dict(bind_vars=bind_vars, count=True, full_count=True)
        execute_kwargs["max_runtime"] = configured_max_runtime

        aql_started = time.perf_counter()
        aql_outcome = "error"
        try:
            cursor = await self.run_sync(db_to_query.aql.execute, aql_query, **execute_kwargs)
            aql_outcome = "success"
        finally:
            observe_aql("execute", aql_outcome, time.perf_counter() - aql_started)
        results = list(cursor)

        response = {
            "query_executed": aql_query,
            "database_queried": database_name,
            "max_runtime": configured_max_runtime,
            "classification": classification.classification.value,
            "count": cursor.count(),
            "full_count": (cursor.full_count() if hasattr(cursor, "full_count") else None),
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
            f"AQLExecutionAgent: Explaining AQL in DB '{database_name}': "
            f"{_aql_log_fragment(aql_query)}"
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
            f"AQLExecutionAgent: Validating AQL in DB '{database_name}': "
            f"{_aql_log_fragment(aql_query)}"
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
