import hashlib
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
from arangodb_mcp.policy.aql_classifier import (
    AQLClassification,
    AQLClassificationResult,
    classify_aql_parse_result,
)
from arangodb_mcp.policy.confirmation import ConfirmationError, consume_conditional_confirmation
from arangodb_mcp.policy.limits import effective_aql_runtime

logger = logging.getLogger(__name__)

# Human-readable description of the equivalence proof, surfaced to callers so a
# speed comparison is never trusted without knowing how "same data" was decided.
_ROW_EQUIVALENCE_METHOD = (
    "Each result row is reduced to a type-tagged canonical string (object keys sorted, "
    "integer-valued floats folded onto integers) and hashed with SHA-256. The per-row "
    "digests are sorted and hashed together into one order-independent multiset "
    "signature; two queries are equivalent when their signatures match."
)


def _canonical_token(value: Any) -> str:
    """Render a JSON-like value as a deterministic, type-tagged canonical string.

    Type tags keep values of different kinds from colliding (the string ``"1"``
    must not look like the integer ``1``). Object keys are emitted in sorted
    order so that field ordering cannot change the token, and integer-valued
    floats collapse onto their integer form so a query that yields ``1`` and one
    that yields ``1.0`` are treated as returning the same datum.
    """
    if value is None:
        return "z"
    if isinstance(value, bool):
        return "b1" if value else "b0"
    if isinstance(value, int):
        return f"i{value!r}"
    if isinstance(value, float):
        if value != value:  # NaN
            return "fnan"
        if value in (float("inf"), float("-inf")):
            return f"f{value!r}"
        if value.is_integer():
            return f"i{int(value)!r}"
        return f"f{value!r}"
    if isinstance(value, str):
        return f"s{value}"
    if isinstance(value, list | tuple):
        return "[" + "\x1e".join(_canonical_token(item) for item in value) + "]"
    if isinstance(value, dict):
        parts = [f"{key!r}\x1f{_canonical_token(value[key])}" for key in sorted(value, key=repr)]
        return "{" + "\x1e".join(parts) + "}"
    return "s" + repr(value)


def _row_digest(row: Any) -> str:
    return hashlib.sha256(_canonical_token(row).encode("utf-8")).hexdigest()


def _multiset_signature(rows: List[Any]) -> str:
    """Fold a result set into one order-independent, multiplicity-preserving digest.

    Sorting the per-row digests removes any dependence on the order the rows were
    returned while still preserving how many times each distinct row occurs, so
    the signature captures the result MULTISET rather than merely its set.
    """
    accumulator = hashlib.sha256()
    for digest in sorted(_row_digest(row) for row in rows):
        accumulator.update(digest.encode("ascii"))
        accumulator.update(b"\n")
    return accumulator.hexdigest()


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

        if operation == "compare":
            return await self._compare(mcp_tool_inputs)

        aql_query: str = mcp_tool_inputs.get("aql_query", "")
        bind_vars: Dict[str, Any] = mcp_tool_inputs.get("bind_vars", {})
        database_name: str | None = mcp_tool_inputs.get("database_name")

        if not aql_query:
            return {"error": "AQL query string cannot be empty."}

        if operation == "explain":
            return await self._explain(aql_query, bind_vars, database_name, mcp_tool_inputs)
        elif operation == "validate":
            return await self._validate(aql_query, database_name)
        elif operation == "profile":
            return await self._profile(aql_query, bind_vars, database_name, mcp_tool_inputs)

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

    # ── Profiling and comparison (read-only, they EXECUTE the query) ──────

    @staticmethod
    def _normalize_profile_level(requested: Any) -> int:
        """Clamp the caller's detail request to 1 (basic) or 2 (full plan)."""
        if requested in (1, "1", "basic", False):
            return 1
        try:
            return 2 if int(requested) >= 2 else 1
        except (TypeError, ValueError):
            return 2

    @staticmethod
    def _policy_denied(classification: AQLClassificationResult) -> Dict[str, Any]:
        """Uniform rejection payload for a non-read or ambiguous query."""
        return {
            "error": (
                "Profiling tools execute the query and are strictly read-only; this query "
                "is a mutation or could not be proven read-only. Use 'explain-aql-query' "
                "to analyze a mutating query without executing it."
            ),
            "error_code": "aql_policy_denied",
            "classification": classification.classification.value,
            "reasons": list(classification.reasons),
            "mutation_nodes": list(classification.mutation_nodes),
        }

    async def _classify(self, db: Any, aql_query: str) -> AQLClassificationResult:
        parse_result = await self.run_sync(db.aql.validate, aql_query)
        return classify_aql_parse_result(parse_result)

    @staticmethod
    def _collect_indexes(plan: Dict[str, Any] | None) -> List[Dict[str, Any]]:
        """Pull the indexes the optimizer actually placed into the plan tree."""
        if not plan:
            return []
        used: List[Dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for node in plan.get("nodes", []):
            indexes = node.get("indexes")
            if not indexes:
                continue
            collection = node.get("collection")
            for index in indexes:
                fingerprint = (
                    collection,
                    index.get("name"),
                    index.get("id"),
                    tuple(index.get("fields", [])),
                )
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                used.append(
                    {
                        "collection": collection,
                        "name": index.get("name"),
                        "type": index.get("type"),
                        "fields": index.get("fields", []),
                        "access_node": node.get("type"),
                    }
                )
        return used

    @staticmethod
    def _scan_summary(stats: Dict[str, Any]) -> Dict[str, Any]:
        """Distil the driver's cursor stats into scan-behaviour highlights."""
        return {
            "documents_full_scanned": stats.get("scanned_full"),
            "index_entries_scanned": stats.get("scanned_index"),
            "documents_filtered": stats.get("filtered"),
            "document_lookups": stats.get("lookups"),
        }

    async def _profile_execute(
        self,
        db: Any,
        aql_query: str,
        bind_vars: Dict[str, Any],
        profile_level: int,
        max_runtime: float,
    ) -> Dict[str, Any]:
        """Execute one proven-read-only query with server-side profiling on.

        Returns a raw measurement bundle (never a full envelope) shared by both
        the single-query and comparison entry points.
        """
        execute_kwargs: Dict[str, Any] = dict(
            bind_vars=bind_vars,
            count=True,
            profile=profile_level,
            max_runtime=max_runtime,
        )
        wall_started = time.perf_counter()
        outcome = "error"
        try:
            cursor = await self.run_sync(db.aql.execute, aql_query, **execute_kwargs)
            rows: List[Any] = await self.run_sync(list, cursor)
            outcome = "success"
        finally:
            observe_aql("profile", outcome, time.perf_counter() - wall_started)
        wall_elapsed = time.perf_counter() - wall_started

        stats: Dict[str, Any] = cursor.statistics() or {}
        plan = cursor.plan()
        return {
            "rows": rows,
            "result_count": cursor.count() if cursor.count() is not None else len(rows),
            "result_signature": _multiset_signature(rows),
            "server_elapsed_seconds": stats.get("execution_time"),
            "wall_clock_seconds": wall_elapsed,
            "peak_memory_bytes": stats.get("peak_memory_usage"),
            "stage_timings": cursor.profile() or {},
            "execution_plan": plan,
            "optimizer_rules_applied": (plan.get("rules", []) if plan else []),
            "indexes_used": self._collect_indexes(plan),
            "scan_statistics": self._scan_summary(stats),
            "cursor_statistics": stats,
            "warnings": cursor.warnings() or [],
        }

    async def _profile(
        self,
        aql_query: str,
        bind_vars: Dict[str, Any],
        database_name: str | None,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        db, database_name = self.resolve_db(database_name)

        logger.info(
            f"AQLExecutionAgent: Profiling AQL in DB '{database_name}': "
            f"{_aql_log_fragment(aql_query)}"
        )

        classification = await self._classify(db, aql_query)
        if classification.classification is not AQLClassification.READ:
            return self._policy_denied(classification)

        profile_level = self._normalize_profile_level(inputs.get("profile_level"))
        max_runtime = effective_aql_runtime(
            inputs.get("max_runtime"), settings.server.default_aql_max_runtime
        )

        measured = await self._profile_execute(db, aql_query, bind_vars, profile_level, max_runtime)

        response = {
            "query_executed": aql_query,
            "database_queried": database_name,
            "classification": classification.classification.value,
            "profile_level": profile_level,
            "max_runtime": max_runtime,
            "result_count": measured["result_count"],
            "results": measured["rows"],
            "server_elapsed_seconds": measured["server_elapsed_seconds"],
            "wall_clock_seconds": measured["wall_clock_seconds"],
            "peak_memory_bytes": measured["peak_memory_bytes"],
            "stage_timings": measured["stage_timings"],
            "execution_plan": measured["execution_plan"],
            "optimizer_rules_applied": measured["optimizer_rules_applied"],
            "indexes_used": measured["indexes_used"],
            "scan_statistics": measured["scan_statistics"],
            "cursor_statistics": measured["cursor_statistics"],
            "warnings": measured["warnings"],
        }
        logger.info(
            f"AQLExecutionAgent: Profile complete, {measured['result_count']} rows, "
            f"level={profile_level}."
        )
        return response

    async def _compare(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        entries: List[Dict[str, Any]] = inputs.get("queries") or []
        if len(entries) < 2:
            return {
                "error": "compare-aql-queries needs at least two labeled queries to compare.",
                "error_code": "invalid_input",
                "query_count": len(entries),
            }

        database_name: str | None = inputs.get("database_name")
        db, database_name = self.resolve_db(database_name)
        max_runtime = effective_aql_runtime(
            inputs.get("max_runtime"), settings.server.default_aql_max_runtime
        )

        logger.info(
            f"AQLExecutionAgent: Comparing {len(entries)} AQL queries in DB '{database_name}'."
        )

        reports: List[Dict[str, Any]] = []
        for position, entry in enumerate(entries):
            label = str(entry.get("label") or f"query_{position + 1}")
            aql_query = entry.get("aql_query", "")
            bind_vars = entry.get("bind_vars") or {}

            if not aql_query:
                reports.append(
                    {
                        "label": label,
                        "profiled": False,
                        "error": "AQL query string cannot be empty.",
                        "error_code": "invalid_input",
                    }
                )
                continue

            try:
                classification = await self._classify(db, aql_query)
                if classification.classification is not AQLClassification.READ:
                    denied = self._policy_denied(classification)
                    denied.update({"label": label, "profiled": False})
                    reports.append(denied)
                    continue

                measured = await self._profile_execute(db, aql_query, bind_vars, 2, max_runtime)
                reports.append(
                    {
                        "label": label,
                        "profiled": True,
                        "classification": classification.classification.value,
                        "result_count": measured["result_count"],
                        "result_signature": measured["result_signature"],
                        "server_elapsed_seconds": measured["server_elapsed_seconds"],
                        "wall_clock_seconds": measured["wall_clock_seconds"],
                        "peak_memory_bytes": measured["peak_memory_bytes"],
                        "indexes_used": measured["indexes_used"],
                        "optimizer_rules_applied": measured["optimizer_rules_applied"],
                        "scan_statistics": measured["scan_statistics"],
                    }
                )
            except Exception as exc:  # per-entry isolation: one bad query must not sink the rest
                logger.error(f"AQLExecutionAgent: compare entry '{label}' failed - {exc}")
                reports.append(
                    {
                        "label": label,
                        "profiled": False,
                        "error": f"Query execution failed: {exc}",
                        "error_code": getattr(exc, "error_code", "aql_execute_error"),
                    }
                )

        return self._summarize_comparison(database_name, max_runtime, reports)

    @staticmethod
    def _summarize_comparison(
        database_name: str,
        max_runtime: float,
        reports: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Group profiled queries by result signature and pick the fastest valid one."""
        profiled = [r for r in reports if r.get("profiled")]

        groups: Dict[str, List[str]] = {}
        for report in profiled:
            groups.setdefault(report["result_signature"], []).append(report["label"])
        equivalence_groups = [sorted(labels) for labels in groups.values()]

        def _elapsed(report: Dict[str, Any]) -> float:
            value = report.get("server_elapsed_seconds")
            if value is None:
                value = report.get("wall_clock_seconds")
            return float(value) if value is not None else float("inf")

        functionally_equivalent = len(profiled) >= 2 and len(groups) == 1
        not_equivalent_warning: str | None = None
        if len(profiled) < 2:
            not_equivalent_warning = (
                "Fewer than two queries executed successfully, so functional equivalence "
                "could not be established. Any speed comparison is unreliable."
            )
        elif not functionally_equivalent:
            not_equivalent_warning = (
                "WARNING: the queries are NOT functionally equivalent — they return different "
                "result sets. A faster query here is NOT a valid optimization; do not treat the "
                "speed ranking as interchangeable."
            )

        # Fastest among a set of mutually-equivalent queries (the largest such group).
        fastest_equivalent: Dict[str, Any] | None = None
        largest_group = max(equivalence_groups, key=len, default=[])
        if len(largest_group) >= 2:
            contenders = [r for r in profiled if r["label"] in set(largest_group)]
            winner = min(contenders, key=_elapsed)
            fastest_equivalent = {
                "label": winner["label"],
                "server_elapsed_seconds": winner.get("server_elapsed_seconds"),
                "wall_clock_seconds": winner.get("wall_clock_seconds"),
                "equivalent_group": largest_group,
            }

        return {
            "database_queried": database_name,
            "max_runtime": max_runtime,
            "query_count": len(reports),
            "profiled_count": len(profiled),
            "per_query": reports,
            "functionally_equivalent": functionally_equivalent,
            "equivalence_groups": equivalence_groups,
            "equivalence_method": _ROW_EQUIVALENCE_METHOD,
            "fastest_equivalent": fastest_equivalent,
            "not_equivalent_warning": not_equivalent_warning,
        }

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
