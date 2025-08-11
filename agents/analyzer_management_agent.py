import logging
from typing import Any, Dict, List, Optional

from arango.exceptions import (
    AnalyzerCreateError,
    AnalyzerDeleteError,
    AnalyzerGetError,
    AnalyzerListError,
    ArangoServerError,
)

from agents.agent_base import ArangoAgentBase
from arango_connector import arango_connector
from config import settings

logger = logging.getLogger(__name__)


class AnalyzerManagementAgent(ArangoAgentBase):
    """Agent for managing ArangoDB text analyzers."""

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        database_name: str = mcp_tool_inputs.get("database_name") or settings.arango.default_db_name
        analyzer_name: Optional[str] = mcp_tool_inputs.get("analyzer_name")

        # For create_analyzer
        analyzer_type: Optional[str] = mcp_tool_inputs.get("analyzer_type")
        properties: Optional[Dict[str, Any]] = mcp_tool_inputs.get(
            "properties"
        )  # Can be Dict or str (for N-Gram)
        features: Optional[List[str]] = mcp_tool_inputs.get("features")

        logger.info(
            f"AnalyzerManagementAgent: Op='{operation}', DB='{database_name}', Analyzer='{analyzer_name}'"
        )

        try:
            if not arango_connector.client:
                return {"error": "ArangoDB client not initialized."}

            db = arango_connector.client.db(
                database_name,
                username=settings.arango.root_username,
                password=settings.arango.root_password,
            )

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
                    return {
                        "error": "For N-Gram analyzer, properties must include 'minN' and 'maxN'."
                    }

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
                    return {
                        "status": f"Analyzer '{analyzer_name}' not found or could not be deleted."
                    }

            elif operation == "get_analyzer_properties":
                if not analyzer_name:
                    return {"error": "Analyzer name is required to get properties."}

                analyzer_def = db.analyzer(analyzer_name)  # this gets the definition
                return {"analyzer_definition": analyzer_def}

            else:
                return {"error": f"Unknown analyzer operation: {operation}"}

        except (
            AnalyzerListError,
            AnalyzerCreateError,
            AnalyzerDeleteError,
            AnalyzerGetError,
            ArangoServerError,
        ) as e:
            logger.error(f"AnalyzerManagementAgent: ArangoDB error - {e}")
            return {
                "error": f"ArangoDB Analyzer Error: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"AnalyzerManagementAgent: Unexpected error - {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}
