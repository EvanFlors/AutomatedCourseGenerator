from __future__ import annotations

import pytest

from cogenai.shared.logging import (
    bind_job_id,
    bind_request_id,
    clear_correlation,
    get_logger,
    request_id_var,
    job_id_var,
)


class TestCorrelationContextVars:
    def test_request_id_var_default_is_none(self):
        clear_correlation()
        assert request_id_var.get() is None

    def test_job_id_var_default_is_none(self):
        clear_correlation()
        assert job_id_var.get() is None

    def test_bind_request_id_sets_value(self):
        token = bind_request_id("rid-123")
        try:
            assert request_id_var.get() == "rid-123"
        finally:
            clear_correlation()

    def test_bind_job_id_sets_value(self):
        clear_correlation()
        bind_job_id("job-abc")
        assert job_id_var.get() == "job-abc"
        clear_correlation()

    def test_clear_correlation_resets_all(self):
        bind_request_id("rid-1")
        bind_job_id("job-1")
        clear_correlation()
        assert request_id_var.get() is None
        assert job_id_var.get() is None


class TestStructuredLogger:
    def test_get_logger_returns_bound_logger(self):
        log = get_logger("test")
        # structlog returns a BoundLogger; we just check it has the standard methods.
        assert hasattr(log, "info")
        assert hasattr(log, "error")
        assert hasattr(log, "warning")


class TestRequestIdMiddleware:
    def _make_app(self):
        from fastapi import FastAPI
        from cogenai.interfaces.api.middleware import RequestIdMiddleware

        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)

        @app.get("/echo")
        async def echo():
            from cogenai.shared.logging import request_id_var
            return {"request_id": request_id_var.get()}

        @app.get("/bound")
        async def bound():
            from cogenai.shared.logging import job_id_var
            bind_job_id("test-job")
            return {"job_id": job_id_var.get()}

        return app

    def test_generates_request_id_when_no_header(self):
        from fastapi.testclient import TestClient
        client = TestClient(self._make_app())
        resp = client.get("/echo")
        assert resp.status_code == 200
        rid = resp.headers.get("x-request-id")
        assert rid is not None and len(rid) > 0
        # The handler observed the same request_id.
        assert resp.json()["request_id"] == rid

    def test_honors_inbound_request_id_header(self):
        from fastapi.testclient import TestClient
        client = TestClient(self._make_app())
        resp = client.get("/echo", headers={"X-Request-Id": "client-trace-001"})
        assert resp.headers["x-request-id"] == "client-trace-001"
        assert resp.json()["request_id"] == "client-trace-001"

    def test_request_id_cleared_after_request(self):
        from fastapi.testclient import TestClient
        from cogenai.shared.logging import clear_correlation, request_id_var
        client = TestClient(self._make_app())
        client.get("/echo")
        # After the request, the middleware should have cleared correlation.
        assert request_id_var.get() is None

    def test_job_id_visible_to_handler(self):
        from fastapi.testclient import TestClient
        client = TestClient(self._make_app())
        resp = client.get("/bound")
        assert resp.json()["job_id"] == "test-job"


class TestRequestIdMiddleware_Integration:
    def test_app_routes_return_request_id_header(self):
        from fastapi.testclient import TestClient
        from cogenai.interfaces.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers

    def test_correlation_id_is_uuid_like_when_generated(self):
        import uuid as _uuid
        from fastapi.testclient import TestClient
        from cogenai.interfaces.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/health")
        rid = resp.headers["x-request-id"]
        # Should parse as UUID.
        _uuid.UUID(rid)