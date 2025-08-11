import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ArangoAgentBase(ABC):
    """Base class for ArangoDB operation agents.
    
    Pure data connector - no LLM dependencies.
    The external LLM (Cursor/Claude) handles intelligence.
    """
    
    def __init__(self):
        """Initialize the agent - no LLM needed."""
        pass

    @abstractmethod
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        The core logic for this agent.
        'mcp_tool_inputs' are the validated arguments received by the MCP tool.
        This method should perform the ArangoDB operation and return a result dictionary.
        """
        pass