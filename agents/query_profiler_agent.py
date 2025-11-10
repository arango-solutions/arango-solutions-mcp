import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import AQLQueryExecuteError, AQLQueryExplainError, ArangoServerError

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector
from config import settings

logger = logging.getLogger(__name__)


class QueryProfilerAgent(ArangoAgentBase):
    """Agent for profiling and analyzing AQL query performance."""

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: str = mcp_tool_inputs.get("database_name") or settings.arango.default_db_name

        logger.info(f"QueryProfilerAgent: Op='{operation}', DB='{database_name}'")

        try:
            if not arango_connector.client:
                return {"error": "ArangoDB client not initialized."}

            db = arango_connector.client.db(
                database_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

            if operation == "profile_query":
                return await self._profile_query(db, mcp_tool_inputs)

            elif operation == "compare_queries":
                return await self._compare_queries(db, mcp_tool_inputs)

            elif operation == "explain_query":
                return await self._explain_query(db, mcp_tool_inputs)

            else:
                return {"error": f"Unknown operation: {operation}"}

        except Exception as e:
            logger.error(f"QueryProfilerAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}

    async def _profile_query(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query with full profiling (profile=2)."""
        aql_query: str = inputs.get("aql_query", "")
        bind_vars: Dict[str, Any] = inputs.get("bind_vars", {})
        profile_level: int = inputs.get("profile_level", 2)

        if not aql_query:
            return {"error": "AQL query string cannot be empty."}

        logger.info(f"Profiling query with profile level {profile_level}: {aql_query[:100]}...")

        try:
            # Execute with profiling enabled
            cursor = db.aql.execute(
                aql_query,
                bind_vars=bind_vars,
                count=True,
                full_count=True,
                profile=profile_level,  # 1 = basic, 2 = full with plan
            )

            # Extract results
            results = [doc for doc in cursor]

            # Build response
            response = {
                "query_executed": aql_query,
                "bind_vars_used": bind_vars,
                "database_queried": db.name,
                "profile_level": profile_level,
                "result_count": len(results),
                "results": results,
            }

            # Get statistics (always available, enhanced with profile=2)
            if hasattr(cursor, "statistics"):
                stats = cursor.statistics()
                response["statistics"] = stats
                response["execution_time_seconds"] = stats.get("executionTime", 0)
                response["peak_memory_bytes"] = stats.get("peakMemoryUsage", 0)

            # Get profile data (timing breakdown by stage)
            if hasattr(cursor, "profile") and profile_level >= 1:
                try:
                    profile_data = cursor.profile()
                    response["profile"] = profile_data
                except Exception as e:
                    logger.warning(f"Could not get profile data: {e}")
                    response["profile"] = None

            # Get execution plan (only with profile=2)
            if hasattr(cursor, "plan") and profile_level >= 2:
                try:
                    plan = cursor.plan()
                    response["execution_plan"] = plan
                    
                    # Extract key information from plan
                    if plan:
                        response["indexes_used"] = self._extract_indexes_from_plan(plan)
                        response["optimization_rules"] = plan.get("rules", [])
                except Exception as e:
                    logger.warning(f"Could not get execution plan: {e}")
                    response["execution_plan"] = None

            # Get counts
            if hasattr(cursor, "count"):
                response["count"] = cursor.count()
            if hasattr(cursor, "full_count"):
                response["full_count"] = cursor.full_count()

            logger.info(f"Query profiling completed successfully")
            return response

        except AQLQueryExecuteError as e:
            logger.error(f"AQL execution error: {e}")
            return {
                "error": f"AQL Execution Error: {e.error_message}",
                "error_code": e.error_code,
                "details": str(e),
            }
        except ArangoServerError as e:
            logger.error(f"ArangoDB server error: {e}")
            return {
                "error": f"ArangoDB Server Error: {e.error_message}",
                "error_code": e.error_code,
                "details": str(e),
            }

    async def _compare_queries(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multiple queries and compare their performance."""
        queries: List[Dict[str, Any]] = inputs.get("queries", [])

        if not queries or len(queries) < 2:
            return {"error": "At least 2 queries required for comparison."}

        logger.info(f"Comparing {len(queries)} queries...")

        results = []
        for idx, query_info in enumerate(queries):
            query_name = query_info.get("name", f"Query {idx + 1}")
            aql_query = query_info.get("query", "")
            bind_vars = query_info.get("bind_vars", {})

            if not aql_query:
                results.append({
                    "query_name": query_name,
                    "error": "Empty query string"
                })
                continue

            # Profile this query
            profile_result = await self._profile_query(db, {
                "aql_query": aql_query,
                "bind_vars": bind_vars,
                "profile_level": 2,
            })

            # Extract key metrics for comparison
            comparison_data = {
                "query_name": query_name,
                "query": aql_query,
                "execution_time_seconds": profile_result.get("execution_time_seconds", 0),
                "peak_memory_bytes": profile_result.get("peak_memory_bytes", 0),
                "result_count": profile_result.get("result_count", 0),
                "indexes_used": profile_result.get("indexes_used", []),
                "optimization_rules_count": len(profile_result.get("optimization_rules", [])),
            }

            # Add statistics if available
            if "statistics" in profile_result:
                stats = profile_result["statistics"]
                comparison_data["statistics"] = {
                    "scanned_full": stats.get("scannedFull", 0),
                    "scanned_index": stats.get("scannedIndex", 0),
                    "filtered": stats.get("filtered", 0),
                    "http_requests": stats.get("httpRequests", 0),
                }

            # Include full profile for detailed analysis
            comparison_data["full_profile"] = profile_result

            results.append(comparison_data)

        # Determine best query
        best_query = min(results, key=lambda x: x.get("execution_time_seconds", float("inf")))

        return {
            "database_queried": db.name,
            "queries_compared": len(results),
            "comparison_results": results,
            "best_query": best_query.get("query_name"),
            "best_execution_time": best_query.get("execution_time_seconds"),
            "performance_summary": self._generate_comparison_summary(results),
        }

    async def _explain_query(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Get execution plan without executing the query."""
        aql_query: str = inputs.get("aql_query", "")
        bind_vars: Dict[str, Any] = inputs.get("bind_vars", {})
        all_plans: bool = inputs.get("all_plans", False)

        if not aql_query:
            return {"error": "AQL query string cannot be empty."}

        logger.info(f"Explaining query (all_plans={all_plans}): {aql_query[:100]}...")

        try:
            # Get execution plan without executing
            plan = db.aql.explain(
                query=aql_query,
                bind_vars=bind_vars,
                all_plans=all_plans,
            )

            response = {
                "query": aql_query,
                "bind_vars_used": bind_vars,
                "database_queried": db.name,
                "all_plans": all_plans,
                "execution_plan": plan,
            }

            # Extract useful information
            if isinstance(plan, dict):
                response["estimated_cost"] = plan.get("estimatedCost", 0)
                response["estimated_nr_items"] = plan.get("estimatedNrItems", 0)
                response["indexes_used"] = self._extract_indexes_from_plan(plan)
                response["optimization_rules"] = plan.get("rules", [])
            elif isinstance(plan, list) and len(plan) > 0:
                # Multiple plans returned
                response["plan_count"] = len(plan)
                response["best_plan_cost"] = min(p.get("estimatedCost", float("inf")) for p in plan)

            logger.info("Query explanation completed successfully")
            return response

        except AQLQueryExplainError as e:
            logger.error(f"AQL explain error: {e}")
            return {
                "error": f"AQL Explain Error: {e.error_message}",
                "error_code": e.error_code,
                "details": str(e),
            }
        except ArangoServerError as e:
            logger.error(f"ArangoDB server error: {e}")
            return {
                "error": f"ArangoDB Server Error: {e.error_message}",
                "error_code": e.error_code,
                "details": str(e),
            }

    def _extract_indexes_from_plan(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract index usage information from execution plan."""
        indexes = []
        
        if not plan:
            return indexes

        # Look for nodes in the plan
        nodes = plan.get("nodes", [])
        if not nodes:
            return indexes

        for node in nodes:
            # Check if this node uses an index
            if "indexes" in node:
                for idx in node["indexes"]:
                    indexes.append({
                        "node_type": node.get("type"),
                        "collection": node.get("collection"),
                        "index_id": idx.get("id"),
                        "index_type": idx.get("type"),
                        "fields": idx.get("fields", []),
                        "unique": idx.get("unique", False),
                        "sparse": idx.get("sparse", False),
                    })

        return indexes

    def _generate_comparison_summary(self, results: List[Dict[str, Any]]) -> str:
        """Generate a human-readable comparison summary."""
        if not results:
            return "No queries to compare."

        summary_lines = []
        
        # Sort by execution time
        sorted_results = sorted(results, key=lambda x: x.get("execution_time_seconds", float("inf")))
        
        fastest = sorted_results[0]
        slowest = sorted_results[-1]
        
        summary_lines.append(f"Fastest: {fastest['query_name']} ({fastest['execution_time_seconds']:.4f}s)")
        summary_lines.append(f"Slowest: {slowest['query_name']} ({slowest['execution_time_seconds']:.4f}s)")
        
        if len(sorted_results) > 1:
            speedup = slowest['execution_time_seconds'] / fastest['execution_time_seconds'] if fastest['execution_time_seconds'] > 0 else 0
            summary_lines.append(f"Performance difference: {speedup:.2f}x")
        
        return "\n".join(summary_lines)

