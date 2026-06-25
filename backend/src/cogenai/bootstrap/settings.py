from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App settings
    app_name: str = "CourseForge"
    app_env: str = Field(default="development", description="The environment in which the app is running.")
    debug: bool = Field(default=False, description="Enable debug mode.")

    # API settings
    api_host: str = Field(default="127.0.0.1", description="The API host.")
    api_port: int = Field(default=8000, description="The API port.")

    # LLM Provider settings
    llm_provider: str = Field(default="stub", description="The LLM provider to use (e.g., 'gemini', 'openai', 'anthropic').")
    openai_api_key: str = Field(default="", description="The API key for OpenAI.")
    anthro_api_key: str = Field(default="", description="The API key for Anthropic.")
    google_api_key: str = Field(default="", description="The API key for Google/Gemini.")

    # Gemini credentials settings
    gemini_use_credentials: bool = Field(default=False, description="Use Google Cloud credentials instead of API key.")
    gemini_location: str = Field(default="us-central1", description="The Google Cloud location for Vertex AI.")
    gemini_scope: str = Field(default="https://www.googleapis.com/auth/cloud-platform", description="The Google Cloud scope.")

    model: str = Field(default="", description="The model to use for the LLM.")
    default_temperature: float = Field(default=0.7, description="The default temperature for the LLM.")
    default_max_tokens: int = Field(default=None, description="The default maximum number of tokens for the LLM.")

    # Generation settings
    max_iterations: int = Field(default=3, description="The maximum number of iterations for the generation process.")
    token_budget_input: int = Field(default=500_000, description="The token budget for the input prompt.")
    token_budget_output: int = Field(default=200_000, description="The token budget for the output response.")

    # Observability
    log_level: str = Field(default="INFO", description="The logging level (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR').")

    def is_production(self) -> bool:
        return self.app_env == "production"

    def is_development(self) -> bool:
        return self.app_env == "development"

    def default_token_budget(self) -> int:
        """Default per-job token budget per ADR-0009 / NFR-COST-001 (input + output)."""
        return int(self.token_budget_input) + int(self.token_budget_output)

settings = Settings()


def get_settings() -> Settings:
    return settings


def default_token_budget() -> int:
    """Module-level helper for callers that don't want to import settings."""
    return get_settings().default_token_budget()
