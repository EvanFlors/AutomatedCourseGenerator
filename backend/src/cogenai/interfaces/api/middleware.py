"""FastAPI middleware for request-scoped correlation IDs.

Adds:
- `X-Request-Id` to every response (echoing the request header if present,
  or generating a fresh UUID otherwise).
- Per-request context binding: `bind_request_id(...)` for the lifetime of
  the request, with `clear_correlation()` on exit.

The bound IDs are picked up automatically by `structlog.contextvars.merge_contextvars`,
so every log line emitted during a request includes `request_id` (and `job_id`
once the handler sets it via `bind_job_id`).
"""
from __future__ import annotations

import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from cogenai.shared.logging import (
    bind_request_id,
    clear_correlation,
    get_logger,
)

_REQUEST_ID_HEADER = "X-Request-Id"
logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Honor inbound X-Request-Id for distributed tracing.
        rid = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = bind_request_id(rid)
        try:
            response: Response = await call_next(request)
            response.headers[_REQUEST_ID_HEADER] = rid
            return response
        finally:
            clear_correlation()
            # Reset the request_id contextvar to avoid leaking across awaits
            # outside the middleware (defensive).
            del token
