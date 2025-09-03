import logging
import os
from typing import Any, Dict

from agents.agent_base import ArangoAgentBase

logger = logging.getLogger(__name__)


class ManualManagementAgent(ArangoAgentBase):
    """Agent for retrieving AQL manuals."""

    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        manual_name: str = mcp_tool_inputs.get("manual_name", "").lower()

        logger.info(f"ManualManagementAgent: Op='{operation}', Manual='{manual_name}'")

        try:
            if operation != "get_aql_manual":
                return {"error": f"Unknown manual operation: {operation}"}

            # Construct the correct path to the manuals
            manuals_dir = "manuals"
            if manual_name == "aql_ref":
                file_path = os.path.join(manuals_dir, "aql_ref.md")
            elif manual_name == "cypher2aql":
                file_path = os.path.join(manuals_dir, "cypher2aql.md")
            elif manual_name == "optimization":
                file_path = os.path.join(manuals_dir, "optimization.md")
            else:
                return {
                    "error": f"Unknown manual name: {manual_name}.  Available manuals: aql_ref, cypher2aql, optimization"
                }

            with open(file_path, "r", encoding="utf-8") as f:
                manual_content = f.read()
            return {"manual_content": manual_content}

        except FileNotFoundError:
            logger.error(f"ManualManagementAgent: Manual file not found: {file_path}")
            return {"error": f"Manual not found."}
        except Exception as e:
            logger.error(f"ManualManagementAgent: Error retrieving manual: {e}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}
