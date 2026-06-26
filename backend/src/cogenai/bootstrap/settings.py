"""Backward-compat shim: cogenai.bootstrap.settings → cogenai.shared.settings."""
from cogenai.shared.settings import *  # noqa: F401,F403
from cogenai.shared.settings import (  # noqa: F401
    Settings,
    default_token_budget,
    get_settings,
)