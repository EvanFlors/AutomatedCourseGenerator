"""Backward-compat shim: cogenai.bootstrap.container → cogenai.infrastructure.container."""
from cogenai.infrastructure.container import *  # noqa: F401,F403
from cogenai.infrastructure.container import (  # noqa: F401
    Container,
    _container,
    get_container,
    get_llm_provider,
)