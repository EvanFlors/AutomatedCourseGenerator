"""Backward-compat shim: cogenai.bootstrap.orchestrator → cogenai.application.run_demo.

This module is a thin alias: every name (public or private) defined in
`cogenai.application.run_demo` is accessible here for backward compatibility.
"""
import sys as _sys

from cogenai.application import run_demo as _mod

# Re-export everything from the new location.
for _name in dir(_mod):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_mod, _name)

# Explicit re-exports for the symbols most commonly imported.
__all__ = [n for n in dir(_mod) if not n.startswith("__")]

# Make `from cogenai.bootstrap.orchestrator import X` work for any X.
_sys.modules[__name__] = _mod