import logging
from importlib import resources
from typing import Any, Dict

from arangodb_mcp.agents.agent_base import ArangoAgentBase, handle_arango_errors

logger = logging.getLogger(__name__)

_MANUALS = resources.files("arangodb_mcp.manuals")
_AVAILABLE_MANUALS = {
    resource.name.removesuffix(".md").lower(): resource
    for resource in _MANUALS.iterdir()
    if resource.name.endswith(".md")
}


class ManualManagementAgent(ArangoAgentBase):
    """Agent for retrieving AQL manuals."""

    @handle_arango_errors(
        "ManualManagementAgent", "Manual", specific_exceptions=(FileNotFoundError,)
    )
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        operation: str = mcp_tool_inputs.get("operation", "")
        manual_name: str = mcp_tool_inputs.get("manual_name", "").lower()

        logger.info(f"ManualManagementAgent: Op='{operation}', Manual='{manual_name}'")

        if operation != "get_aql_manual":
            return {"error": f"Unknown manual operation: {operation}"}

        file_path = _AVAILABLE_MANUALS.get(manual_name)
        if file_path is None:
            available = ", ".join(sorted(_AVAILABLE_MANUALS.keys()))
            return {"error": f"Unknown manual '{manual_name}'. Available: {available}"}

        manual_content = await self.run_sync(file_path.read_text, encoding="utf-8")
        return {"manual_content": manual_content}
