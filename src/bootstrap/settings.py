from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = Field(
        default="sqlite+aiosqlite:///./course_automation.db",
        description="Async SQLAlchemy database URL.",
    )
    database_url_sync: str = Field(
        default="sqlite:///./course_automation.db",
        description="Sync SQLAlchemy database URL (used by Alembic).",
    )
    database_echo: bool = False

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me-in-production"

    gemini_api_key: str = "your-gemini-api-key"
    llm_model: str = "gemini-2.0-flash-exp"
    embedding_model: str = "text-embedding-004"
    embedding_dim: int = 768

    generation_max_tokens: int = 8192
    generation_temperature: float = 0.7
    graph_max_concepts_per_topic: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
