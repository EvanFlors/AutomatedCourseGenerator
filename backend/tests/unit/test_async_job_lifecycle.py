from __future__ import annotations

import pytest

from cogenai.bootstrap.app import create_app


class _StubProvider:
    """Minimal stub that returns a valid JSON evaluator response."""

    def __init__(self):
        self.health_ok = True

    def health_check(self) -> bool:
        return self.health_ok

    def complete(self, request):
        from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
        # Return a minimal but valid response; agents will produce partial data
        # but the orchestration loop must complete (with failures, not hangs).
        return CompletionResponse(
            text='{"ok": true}',
            model=request.model,
            usage=CompletionUsage(input_tokens=10, output_tokens=10, total_tokens=20),
            finish_reason="stop",
        )


@pytest.fixture(autouse=True)
def _stub_llm_provider(monkeypatch):
    """Replace get_llm_provider with the stub for the duration of each test.

    Patches the symbol in:
    - cogenai.bootstrap.container (canonical)
    - cogenai.bootstrap.orchestrator (used by orchestrator.run_demo)
    """
    from cogenai.bootstrap import container
    from cogenai.bootstrap import orchestrator
    monkeypatch.setattr(container, "get_llm_provider", lambda: _StubProvider())
    monkeypatch.setattr(orchestrator, "get_llm_provider", lambda: _StubProvider())
    yield


class TestAsyncJobLifecycle:
    """FR-CG-004: POST /v1/courses → job_id; GET /v1/jobs/{id} → status."""

    def test_post_courses_returns_job_id(self):
        from fastapi.testclient import TestClient
        from cogenai.bootstrap.jobs import get_job_store
        get_job_store().clear()
        client = TestClient(create_app())
        resp = client.post("/v1/courses", json={
            "topic": "Python",
            "audience": "beginner",
            "difficulty": "beginner",
            "learning_outcomes": ["Variables"],
            "max_iterations": 1,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "queued"

    def test_post_courses_is_idempotent(self):
        from fastapi.testclient import TestClient
        from cogenai.bootstrap.jobs import get_job_store
        get_job_store().clear()
        client = TestClient(create_app())
        payload = {
            "topic": "Python",
            "audience": "beginner",
            "difficulty": "beginner",
            "learning_outcomes": ["Variables"],
            "max_iterations": 1,
        }
        a = client.post("/v1/courses", json=payload).json()
        b = client.post("/v1/courses", json=payload).json()
        assert a["job_id"] == b["job_id"]

    def test_get_unknown_job_returns_404(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.get("/v1/jobs/missing")
        assert resp.status_code == 404

    def test_get_job_returns_terminal_state(self):
        from fastapi.testclient import TestClient
        from cogenai.bootstrap.jobs import JobStatus, get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        submit = client.post("/v1/courses", json={
            "topic": "Python",
            "audience": "beginner",
            "difficulty": "beginner",
            "learning_outcomes": ["Variables"],
            "max_iterations": 1,
        }).json()
        job_id = submit["job_id"]

        # BackgroundTasks runs synchronously in TestClient (no event loop),
        # so by the time we poll the job is already terminal.
        for _ in range(50):
            job = store.get(job_id)
            if job is not None and job.status in (
                JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.PARTIAL,
            ):
                break

        polled = client.get(f"/v1/jobs/{job_id}")
        assert polled.status_code == 200
        body = polled.json()
        assert body["status"] in ("completed", "failed", "partial")
        if body["status"] == "failed":
            assert body["error"]
        else:
            assert body["termination_reason"] in (
                "quality_threshold", "max_iterations", "budget_exhausted", "user_aborted",
            )

    def test_post_courses_validates_request(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.post("/v1/courses", json={"topic": "Python"})
        assert resp.status_code == 422

    def test_post_courses_with_assignments(self):
        from fastapi.testclient import TestClient
        from cogenai.bootstrap.jobs import get_job_store
        get_job_store().clear()
        client = TestClient(create_app())
        resp = client.post("/v1/courses", json={
            "topic": "Python",
            "audience": "beginner",
            "difficulty": "beginner",
            "learning_outcomes": ["Variables"],
            "max_iterations": 1,
            "agent_assignments": {"evaluator": "gpt-4"},
        })
        assert resp.status_code == 200