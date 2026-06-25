from pathlib import Path

from cogenai.bootstrap.container import Container, _container, get_container, get_llm_provider
from cogenai.bootstrap.logging import (
    bind_job_id,
    bind_request_id,
    clear_correlation,
    configure_logging,
    get_logger,
)
from cogenai.bootstrap.settings import Settings, default_token_budget, get_settings
from cogenai.prompt import load_prompts

# Load YAML prompts at startup. Falls back to in-code if directory missing.
_PROMPTS_LOADED = load_prompts(Path(__file__).resolve().parent.parent / "prompt")

__all__ = [
    "_PROMPTS_LOADED",
    "Container",
    "Settings",
    "_container",
    "bind_job_id",
    "bind_request_id",
    "clear_correlation",
    "configure_logging",
    "get_container",
    "get_llm_provider",
    "get_logger",
    "get_settings",
    "load_prompts",
]
