from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClientAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    mcp_server_url: HttpUrl = Field(
        ..., env="MCP_SERVER_URL"
    )  # e.g., "http://localhost:8000/mcp"
    llm_model_name: str = "gemini-2.0-flash"  # For the orchestrator
    # For main conversation, use chat-bison-001 or a newer chat model
    # For specific tasks inside agents, can use text-bison-001 or others
    # Adjust based on availability and Gemini API updates.
    # Let's use gemini-2.0-flash as a capable default for the orchestrator.


client_settings = ClientAppSettings()
