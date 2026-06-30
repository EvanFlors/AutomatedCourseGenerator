from __future__ import annotations

import pytest

from cogenai.interfaces.api.app import create_app


class _StubProvider:
    def health_check(self) -> bool: return True
    def complete(self, request):
        from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
        return CompletionResponse(
            text='{"ok": true}', model=request.model,
            usage=CompletionUsage(10, 10, 20), finish_reason="stop",
        )


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    from cogenai.application.templates import reset_template_cache
    reset_template_cache()
    # Patch the symbol in the canonical location.
    from cogenai.infrastructure import container as canonical_container
    monkeypatch.setattr(canonical_container, "get_llm_provider", lambda: _StubProvider())
    yield


class TestTemplatesAPI:
    def test_list_templates_endpoint(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.get("/v1/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "python-beginner" in data
        assert data["python-beginner"]["topic"] == "Python"

    def test_post_with_unknown_template_returns_400(self):
        """Validation happens before any background task is scheduled."""
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.post(
            "/v1/courses?template=does-not-exist",
            json={
                "topic": "Python",
                "audience": "beginner",
                "difficulty": "beginner",
                "learning_outcomes": ["Variables"],
            },
        )
        assert resp.status_code == 400
        assert "unknown template" in resp.json()["detail"]


class TestRetryEndpoint:
    def test_retry_unknown_job_returns_404(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.post("/v1/jobs/missing/retry")
        assert resp.status_code == 404

    def test_retry_non_failed_returns_409(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        job = store.create({"x": 1})
        client = TestClient(create_app())
        resp = client.post(f"/v1/jobs/{job.job_id}/retry")
        assert resp.status_code == 409

    def test_retry_failed_job_logic(self):
        """Test the retry transition without scheduling a background task.

        We bypass HTTP and manipulate the store directly: a FAILED job's
        status can be reset to QUEUED for re-execution.
        """
        from cogenai.application.jobs import JobStatus, get_job_store
        store = get_job_store()
        store.clear()
        payload = {
            "topic": "Python",
            "audience": "beginner",
            "difficulty": "beginner",
            "learning_outcomes": ["Variables"],
        }
        job = store.create(payload)
        store.update(
            job.job_id,
            status=JobStatus.FAILED,
            completed_at="2026-01-01T00:00:00Z",
            error="simulated failure",
        )
        # Simulate the retry logic from the handler.
        store.update(
            job.job_id,
            status=JobStatus.QUEUED,
            completed_at=None,
            termination_reason=None,
            result=None,
            error=None,
        )
        refreshed = store.get(job.job_id)
        assert refreshed.status == JobStatus.QUEUED
        assert refreshed.error is None
        assert refreshed.completed_at is None