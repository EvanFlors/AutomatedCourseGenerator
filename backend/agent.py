#!/usr/bin/env python3
"""Thin CLI shim. The real implementation lives in
`cogenai.bootstrap.orchestrator` (added in Sprint 5 so the module
graph is owned by the package, not by a top-level script).
"""
import sys

from cogenai.bootstrap.orchestrator import main


if __name__ == "__main__":
    sys.exit(main())