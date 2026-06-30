"""Entrypoint for `python -m cogenai.interfaces.cli [args]`."""
import sys

from cogenai.interfaces.cli.main import main

sys.exit(main())