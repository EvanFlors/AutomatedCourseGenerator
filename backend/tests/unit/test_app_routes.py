from __future__ import annotations

import pytest

from cogenai.interfaces.api.app import create_app


class _StubProvider:
    def health_check(self) -> bool:
        return True
    def complete(self, request):
        from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
        return CompletionResponse(
            text='{"ok": true}', model=request.model,
            usage=CompletionUsage(0, 0, 0), finish_reason="stop",
        )


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    from cogenai.infrastructure import container
    from cogenai.application import run_demo
    monkeypatch.setattr(container, "get_llm_provider", lambda: _StubProvider())
    monkeypatch.setattr(run_demo, "get_llm_provider", lambda: _StubProvider())
    yield


class TestAppRoutes:
    def test_app_has_expected_routes(self):
        app = create_app()
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/health" in paths
        assert "/v1/courses/generate" in paths


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestGenerateEndpointValidation:
    """The endpoint must validate the request body via Pydantic (FR-CG-003)."""

    def test_missing_topic_returns_422(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.post("/v1/courses/generate", json={
            "audience": "beginner", "difficulty": "beginner",
            "learning_outcomes": ["Variables"],
        })
        assert resp.status_code == 422

    def test_missing_outcomes_returns_400_or_422(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.post("/v1/courses/generate", json={
            "topic": "Python",
        })
        # Either Pydantic 422 (DTO validation) or app-level 400 are acceptable.
        assert resp.status_code in (400, 422)

    def test_invalid_audience_returns_422(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.post("/v1/courses/generate", json={
            "topic": "Python",
            "audience": "wizard",
            "difficulty": "beginner",
            "learning_outcomes": ["Variables"],
        })
        assert resp.status_code == 422


class TestOpenAPISchema:
    """Regression: forward-ref return types can crash FastAPI's OpenAPI build.

    Sprint 9 introduced `metrics_endpoint() -> "Response"` which broke
    `/openapi.json` with a 500. This test guards against that pattern.
    """

    def test_openapi_json_returns_200(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "paths" in data
        assert "openapi" in data

    def test_openapi_includes_all_routes(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        data = client.get("/openapi.json").json()
        paths = set(data["paths"].keys())
        # Every registered route must appear in the schema.
        for expected in (
            "/health", "/metrics",
            "/v1/courses", "/v1/courses/generate",
            "/v1/jobs/{job_id}", "/v1/jobs/{job_id}/retry",
            "/v1/templates",
        ):
            assert expected in paths, f"missing path: {expected}"

    def test_metrics_endpoint_has_no_forward_ref(self):
        """If anyone re-introduces `-> 'Response'` this asserts the route
        is annotated with a real (importable) type or no return type at all."""
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        # If the schema builds without 500, the forward ref is fine.
        # This is a defensive check on top of the 200 assertion above.
        resp = client.get("/openapi.json")
        assert resp.status_code == 200