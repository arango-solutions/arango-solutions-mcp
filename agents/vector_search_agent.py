import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import AQLQueryExecuteError, ArangoServerError

from agents.agent_base import ArangoAgentBase
from aql_utils import validate_aql_identifier, validate_aql_identifiers
from arango_connector import arango_connector

logger = logging.getLogger(__name__)

_METRIC_FUNCTIONS = {
    "cosine": ("APPROX_NEAR_COSINE", "DESC"),
    "l2": ("APPROX_NEAR_L2", ""),
    "innerProduct": ("APPROX_NEAR_INNER_PRODUCT", "DESC"),
}


class VectorSearchAgent(ArangoAgentBase):
    """Agent for ArangoDB vector similarity search (ANN).

    Generates and executes AQL queries using APPROX_NEAR_* functions
    against collections with vector indexes.
    """

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")

        logger.info(f"VectorSearchAgent: Op='{operation}', DB='{database_name}'")

        try:
            db = arango_connector.get_db(database_name)
            database_name = database_name or db.name

            if operation == "vector_search":
                return self._execute_vector_search(db, mcp_tool_inputs)

            elif operation == "hybrid_search":
                return self._execute_hybrid_search(db, mcp_tool_inputs)

            else:
                return {"error": f"Unknown vector operation: {operation}"}

        except AQLQueryExecuteError as e:
            logger.error(f"VectorSearchAgent: AQL error - {e}")
            return {
                "error": f"AQL Execution Error: {e.error_message}",
                "error_code": e.error_code,
            }
        except ArangoServerError as e:
            logger.error(f"VectorSearchAgent: ArangoDB error - {e}")
            return {
                "error": f"ArangoDB Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"VectorSearchAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}

    def _execute_vector_search(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        collection_name: str = inputs.get("collection_name", "")
        vector_field: str = inputs.get("vector_field", "")
        query_vector: List[float] = inputs.get("query_vector", [])
        metric: str = inputs.get("metric", "cosine")
        limit: int = inputs.get("limit", 10)
        n_probe: Optional[int] = inputs.get("n_probe")
        return_fields: Optional[List[str]] = inputs.get("return_fields")
        filters: Optional[Dict[str, Any]] = inputs.get("filters")
        include_similarity: bool = inputs.get("include_similarity", True)

        if not collection_name:
            return {"error": "collection_name is required."}
        if not vector_field:
            return {"error": "vector_field is required."}
        if not query_vector:
            return {"error": "query_vector is required (array of numbers)."}
        if metric not in _METRIC_FUNCTIONS:
            return {
                "error": f"Unsupported metric '{metric}'. "
                f"Use: {', '.join(_METRIC_FUNCTIONS.keys())}"
            }

        validate_aql_identifier(collection_name, "collection_name")
        validate_aql_identifier(vector_field, "vector_field")
        if return_fields:
            validate_aql_identifiers(return_fields, "return_field")
        if filters:
            validate_aql_identifiers(list(filters.keys()), "filter_key")

        func_name, sort_dir = _METRIC_FUNCTIONS[metric]
        sort_clause = f"SORT similarity {sort_dir}" if sort_dir else "SORT similarity"

        options_str = ""
        bind_vars: Dict[str, Any] = {
            "@collection": collection_name,
            "qvec": query_vector,
            "lim": int(limit),
        }
        if n_probe is not None:
            options_str = ", { nProbe: @nprobe }"
            bind_vars["nprobe"] = int(n_probe)

        # Build filter clause
        filter_lines = ""
        if filters:
            filter_parts = []
            for i, (key, val) in enumerate(filters.items()):
                var_name = f"fv{i}"
                filter_parts.append(f"FILTER doc.`{key}` == @{var_name}")
                bind_vars[var_name] = val
            filter_lines = "\n  ".join(filter_parts)

        # Build return clause
        if return_fields:
            field_projections = ", ".join(f'"{f}": doc.`{f}`' for f in return_fields)
            if include_similarity:
                return_expr = f"MERGE({{ similarity, {field_projections} }}, {{ _key: doc._key, _id: doc._id }})"
            else:
                return_expr = f"{{ {field_projections}, _key: doc._key, _id: doc._id }}"
        else:
            return_expr = "MERGE({ similarity }, doc)" if include_similarity else "doc"

        filter_block = f"\n  {filter_lines}" if filter_lines else ""

        aql = (
            f"FOR doc IN @@collection{filter_block}\n"
            f"  LET similarity = {func_name}(doc.`{vector_field}`, @qvec{options_str})\n"
            f"  {sort_clause}\n"
            f"  LIMIT @lim\n"
            f"  RETURN {return_expr}"
        )

        logger.info(f"VectorSearchAgent: Executing AQL: {aql[:200]}...")

        cursor = db.aql.execute(aql, bind_vars=bind_vars, count=True)
        results = list(cursor)

        return {
            "results": results,
            "count": len(results),
            "metric": metric,
            "limit": limit,
            "aql_generated": aql,
        }

    def _execute_hybrid_search(self, db, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Hybrid search combining vector similarity with ArangoSearch text filters."""
        collection_name: str = inputs.get("collection_name", "")
        vector_field: str = inputs.get("vector_field", "")
        query_vector: List[float] = inputs.get("query_vector", [])
        metric: str = inputs.get("metric", "cosine")
        limit: int = inputs.get("limit", 10)
        n_probe: Optional[int] = inputs.get("n_probe")
        text_field: Optional[str] = inputs.get("text_field")
        text_query: Optional[str] = inputs.get("text_query")
        text_analyzer: str = inputs.get("text_analyzer", "text_en")
        view_name: Optional[str] = inputs.get("view_name")
        vector_weight: float = inputs.get("vector_weight", 0.7)
        text_weight: float = inputs.get("text_weight", 0.3)

        if not collection_name:
            return {"error": "collection_name is required."}
        if not vector_field:
            return {"error": "vector_field is required."}
        if not query_vector:
            return {"error": "query_vector is required."}
        if metric not in _METRIC_FUNCTIONS:
            return {
                "error": f"Unsupported metric '{metric}'. "
                f"Use: {', '.join(_METRIC_FUNCTIONS.keys())}"
            }

        validate_aql_identifier(collection_name, "collection_name")
        validate_aql_identifier(vector_field, "vector_field")
        if view_name:
            validate_aql_identifier(view_name, "view_name")
        if text_field:
            validate_aql_identifier(text_field, "text_field")
        validate_aql_identifier(text_analyzer, "text_analyzer")

        func_name, sort_dir = _METRIC_FUNCTIONS[metric]
        options_str = ""

        bind_vars: Dict[str, Any] = {
            "@collection": collection_name,
            "qvec": query_vector,
            "lim": int(limit),
            "lim3": int(limit * 3),
            "vec_w": float(vector_weight),
            "txt_w": float(text_weight),
        }
        if n_probe is not None:
            options_str = ", { nProbe: @nprobe }"
            bind_vars["nprobe"] = int(n_probe)

        if text_field and text_query and view_name:
            bind_vars["text_query"] = text_query
            aql = (
                f"LET vec_results = (\n"
                f"  FOR doc IN @@collection\n"
                f"    LET sim = {func_name}(doc.`{vector_field}`, @qvec{options_str})\n"
                f"    SORT sim {sort_dir}\n"
                f"    LIMIT @lim3\n"
                f"    RETURN {{ _key: doc._key, vec_score: sim }}\n"
                f")\n"
                f"LET text_results = (\n"
                f"  FOR doc IN `{view_name}`\n"
                f'    SEARCH ANALYZER(doc.`{text_field}` IN TOKENS(@text_query, "{text_analyzer}"), "{text_analyzer}")\n'
                f"    SORT BM25(doc) DESC\n"
                f"    LIMIT @lim3\n"
                f"    RETURN {{ _key: doc._key, text_score: BM25(doc) }}\n"
                f")\n"
                f"FOR vr IN vec_results\n"
                f"  FOR tr IN text_results\n"
                f"    FILTER vr._key == tr._key\n"
                f"    LET combined = vr.vec_score * @vec_w + tr.text_score * @txt_w\n"
                f"    SORT combined DESC\n"
                f"    LIMIT @lim\n"
                f"    LET full_doc = DOCUMENT(@@collection, vr._key)\n"
                f"    RETURN MERGE(full_doc, {{ vec_score: vr.vec_score, text_score: tr.text_score, combined_score: combined }})"
            )
        else:
            return self._execute_vector_search(db, inputs)

        logger.info(f"VectorSearchAgent: Executing hybrid AQL: {aql[:200]}...")

        cursor = db.aql.execute(aql, bind_vars=bind_vars, count=True)
        results = list(cursor)

        return {
            "results": results,
            "count": len(results),
            "metric": metric,
            "limit": limit,
            "vector_weight": vector_weight,
            "text_weight": text_weight,
            "aql_generated": aql,
        }
