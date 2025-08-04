from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ArangoDBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARANGO_", env_file=".env", extra="ignore"
    )

    hosts: str = "http://localhost:8529"
    root_username: str = "root"
    root_password: str = "123"
    default_db_name: str = "_system"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")


class AppSettings(BaseSettings):
    arango: ArangoDBSettings = ArangoDBSettings()
    llm: LLMSettings = LLMSettings()


# Load settings once
settings = AppSettings()
