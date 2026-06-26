"""Backward-compat shims. Modules have moved to clean-architecture layers:

- cogenai.bootstrap.container → cogenai.infrastructure.container
- cogenai.bootstrap.logging    → cogenai.shared.logging
- cogenai.bootstrap.settings   → cogenai.shared.settings
- cogenai.bootstrap.jobs       → cogenai.application.jobs
- cogenai.bootstrap.orchestrator → cogenai.application.orchestrator
- cogenai.bootstrap.app        → cogenai.interfaces.api.app

This __init__ keeps the historical import surface working.
"""
from pathlib import Path

from cogenai.bootstrap.app import create_app  # re-export
from cogenai.bootstrap.container import (  # re-export
    Container,
    _container,
    get_container,
    get_llm_provider,
)
from cogenai.bootstrap.logging import (  # re-export
    bind_job_id,
    bind_request_id,
    clear_correlation,
    configure_logging,
    get_logger,
)
from cogenai.application.run_demo import run_demo  # re-export
from cogenai.bootstrap.settings import (  # re-export
    Settings,
    default_token_budget,
    get_settings,
)
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
    "create_app",
    "get_container",
    "get_llm_provider",
    "get_logger",
    "get_settings",
    "load_prompts",
    "run_demo",
]