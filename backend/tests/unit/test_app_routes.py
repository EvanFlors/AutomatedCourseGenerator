from __future__ import annotations

import pytest

from cogenai.bootstrap.app import create_app


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
    from cogenai.bootstrap import container
    from cogenai.bootstrap import orchestrator
    monkeypatch.setattr(container, "get_llm_provider", lambda: _StubProvider())
    monkeypatch.setattr(orchestrator, "get_llm_provider", lambda: _StubProvider())
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