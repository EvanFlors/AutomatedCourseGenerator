"""Backward-compat shim: cogenai.bootstrap.app → cogenai.interfaces.api.app."""
from cogenai.interfaces.api.app import *  # noqa: F401,F403
from cogenai.interfaces.api.app import create_app  # noqa: F401