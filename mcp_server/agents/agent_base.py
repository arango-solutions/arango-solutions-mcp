import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool as LangchainBaseTool
from langchain_google_genai import ChatGoogleGenerativeAI  # Specific import

from ..config import settings

logger = logging.getLogger(__name__)


class ArangoAgentBase(ABC):
    def __init__(
        self, llm_model_name: str = "gemini-2.0-flash"
    ):  # Default to a capable model
        self.api_key = settings.llm.gemini_api_key
        self.model_name = llm_model_name
        self.llm: BaseChatModel = self._initialize_llm()
        # Langchain tools for internal agent use, if any. Most will use python-arango directly.
        self.langchain_tools: List[LangchainBaseTool] = (
            self._setup_internal_langchain_tools()
        )

    def _initialize_llm(self) -> BaseChatModel:
        """Initializes and returns the LLM instance for this agent."""
        return ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=self.api_key,
            convert_system_message_to_human=True,
        )

    def _setup_internal_langchain_tools(self) -> List[LangchainBaseTool]:
        """
        Sets up and returns a list of Langchain tools IF this specific agent
        needs to perform complex internal reasoning using Langchain's tool use.
        Often, this will be an empty list, and the agent will directly use python-arango.
        """
        return []

    @abstractmethod
    async def arun(self, mcp_tool_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        The core logic for this agent.
        'mcp_tool_inputs' are the validated arguments received by the MCP tool.
        This method should perform the ArangoDB operation and return a result dictionary.
        It may use self.llm for understanding/transforming inputs or formatting outputs.
        """
        pass
