"""
Configuration management using Pydantic Settings
"""
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Environment
    environment: Literal["development", "production", "testing"] = "development"
    
    # Server Configuration
    reasoner_pod_host: str = Field(default="0.0.0.0", alias="host")
    reasoner_pod_port: int = Field(default=8000, alias="port")
    
    # OpenCode Server Configuration
    opencode_base_url: str = "http://host.docker.internal:4099"
    opencode_provider: str = "openai"
    opencode_model: str = "gpt-4o"  # Changed from gpt-4o due to context length issues
    opencode_timeout: int = 120  # seconds
    
    # Job Configuration
    max_steps_per_job: int = 50
    checkpoint_interval: int = 5  # Save checkpoint every N steps
    job_timeout: int = 3600  # seconds
    
    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    
    # Data Persistence
    checkpoint_dir: str = "/app/data/checkpoints"
    logs_dir: str = "/app/data/logs"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == "production"


# Global settings instance
settings = Settings()


