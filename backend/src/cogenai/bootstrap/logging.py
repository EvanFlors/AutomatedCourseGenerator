"""Backward-compat shim: cogenai.bootstrap.logging → cogenai.shared.logging."""
from cogenai.shared.logging import *  # noqa: F401,F403
from cogenai.shared.logging import (  # noqa: F401
    bind_job_id,
    bind_request_id,
    clear_correlation,
    configure_logging,
    get_logger,
)