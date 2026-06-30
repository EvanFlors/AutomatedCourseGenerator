"""CLI surface (re-exports). See `main.py` for the entrypoint."""
from cogenai.interfaces.cli.main import (  # noqa: F401
    IterationResult,
    main,
    parse_args,
    print_final_course,
    print_iteration_summary,
    run_demo,
)