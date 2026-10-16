"""Application configuration settings using Pydantic v2 Settings."""

from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "NexusAct"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_VERSION: str = "0.2.0"
    NEXUSACT_REPOSITORY_PATH: str = "."

    # API Server
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"

    # FalkorDB Database
    FALKORDB_HOST: str = "127.0.0.1"
    FALKORDB_PORT: int = 6379
    FALKORDB_PASSWORD: str = ""
    FALKORDB_PRIMARY_GRAPH: str = "nexusact_main"
    FALKORDB_CONNECTION_TIMEOUT_MS: int = 5000

    # MCP Server
    MCP_SERVER_HOST: str = "127.0.0.1"
    MCP_SERVER_PORT: int = 8001
    MCP_LOG_LEVEL: str = "INFO"

    # Frontend
    VITE_API_BASE_URL: str = "http://localhost:8000"

    # AI Provider (Phase 1: disabled by default)
    LLM_PROVIDER: str = "none"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = ""
    OPENAI_API_KEY: str = ""

    # GitHub (Phase 1: disabled / unused)
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @field_validator("FALKORDB_PRIMARY_GRAPH")
    @classmethod
    def validate_graph_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("FALKORDB_PRIMARY_GRAPH must not be empty.")
        return v.strip()


# Global cached settings instance
settings = Settings()
