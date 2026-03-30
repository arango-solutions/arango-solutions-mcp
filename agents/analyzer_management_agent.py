import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import (
    AnalyzerCreateError,
    AnalyzerDeleteError,
    AnalyzerGetError,
    AnalyzerListError,
)

from agents.agent_base import ArangoAgentBase, handle_arango_errors
from arango_connector import arango_connector

logger = logging.getLogger(__name__)


class AnalyzerManagementAgent(ArangoAgentBase):
    """Agent for managing ArangoDB text analyzers."""

    @handle_arango_errors(
        "AnalyzerManagementAgent",
        "ArangoDB Analyzer",
        (AnalyzerListError, AnalyzerCreateError, AnalyzerDeleteError, AnalyzerGetError),
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: Optional[str] = mcp_tool_inputs.get("database_name")
        analyzer_name: Optional[str] = mcp_tool_inputs.get("analyzer_name")

        analyzer_type: Optional[str] = mcp_tool_inputs.get("analyzer_type")
        properties: Optional[Dict[str, Any]] = mcp_tool_inputs.get("properties")
        features: Optional[List[str]] = mcp_tool_inputs.get("features")

        logger.info(
            f"AnalyzerManagementAgent: Op='{operation}', DB='{database_name}', Analyzer='{analyzer_name}'"
        )

        db = arango_connector.get_db(database_name)

        if operation == "list_analyzers":
            analyzers = db.analyzers()
            return {"analyzers": analyzers}

        elif operation == "create_analyzer":
            if not analyzer_name or not analyzer_type:
                return {"error": "Analyzer name and type are required for creation."}

            # Basic validation for N-Gram analyzer
            if (
                analyzer_type == "ngram"
                and isinstance(properties, dict)
                and ("minN" not in properties or "maxN" not in properties)
            ):
                return {"error": "For N-Gram analyzer, properties must include 'minN' and 'maxN'."}

            analyzer_info = db.create_analyzer(
                name=analyzer_name,
                analyzer_type=analyzer_type,
                properties=properties or {},
                features=features or [],
            )
            return {"status": "Analyzer created successfully.", "analyzer_info": analyzer_info}

        elif operation == "delete_analyzer":
            if not analyzer_name:
                return {"error": "Analyzer name is required for deletion."}

            success = db.delete_analyzer(
                analyzer_name, ignore_missing=True
            )  # Set ignore_missing based on desired behavior
            if success:  # delete_analyzer returns True/False
                return {"status": f"Analyzer '{analyzer_name}' deleted successfully."}
            else:
                return {"status": f"Analyzer '{analyzer_name}' not found or could not be deleted."}

        elif operation == "get_analyzer_properties":
            if not analyzer_name:
                return {"error": "Analyzer name is required to get properties."}

            analyzer_def = db.analyzer(analyzer_name)  # this gets the definition
            return {"analyzer_definition": analyzer_def}

        else:
            return {"error": f"Unknown analyzer operation: {operation}"}
