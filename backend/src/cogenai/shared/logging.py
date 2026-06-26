import logging
from contextvars import ContextVar

import structlog

from cogenai.shared.settings import settings

# Correlation IDs for tracing
request_id_var: ContextVar[str] = ContextVar("request_id", default=None)
job_id_var: ContextVar[str] = ContextVar("job_id", default=None)
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[str] = ContextVar("user_id", default=None)


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level),
    )

    if settings.is_production():
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def bind_job_id(job_id: str) -> None:
    job_id_var.set(job_id)


def clear_correlation() -> None:
    request_id_var.set(None)
    job_id_var.set(None)
    tenant_id_var.set(None)
    user_id_var.set(None)


# Configure on import
configure_logging()
