from __future__ import annotations

import json
import time

import pytest

from cogenai.interfaces.api.app import create_app


class _StubProvider:
    def __init__(self, response_text: str = '{"ok": true}'):
        self.response_text = response_text
        self.call_count = 0

    def health_check(self) -> bool:
        return True

    def complete(self, request):
        from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
        self.call_count += 1
        return CompletionResponse(
            text=self.response_text,
            model=request.model,
            usage=CompletionUsage(input_tokens=10, output_tokens=10, total_tokens=20),
            finish_reason="stop",
        )


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    from cogenai.infrastructure import container
    monkeypatch.setattr(container, "get_llm_provider", lambda: _StubProvider())
    try:
        from cogenai.application import run_demo
        monkeypatch.setattr(run_demo, "get_llm_provider", lambda: _StubProvider())
    except ImportError:
        pass
    from cogenai.application.jobs import get_job_store
    get_job_store().clear()
    yield


class TestCancellationAPI:
    def test_delete_unknown_job_returns_404(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.delete("/v1/jobs/missing")
        assert resp.status_code == 404

    def test_delete_queued_job_marks_aborted(self):
        """DELETE on a non-terminal job returns 200 with status=aborted.

        BackgroundTasks runs synchronously in TestClient, so by the time we
        call DELETE the job may already be in a terminal state. We test the
        DELETE path directly via the JobStore.
        """
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        # Directly create a queued job (bypasses POST so no background task).
        job = store.create({"topic": "Python", "learning_outcomes": ["x"]})
        client = TestClient(create_app())
        resp = client.delete(f"/v1/jobs/{job.job_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"

    def test_delete_aborted_job_returns_409(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        job = store.create({"x": 1})
        client = TestClient(create_app())
        client.delete(f"/v1/jobs/{job.job_id}")
        resp = client.delete(f"/v1/jobs/{job.job_id}")
        assert resp.status_code == 409

    def test_get_after_delete_shows_aborted(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        job = store.create({"x": 1})
        client = TestClient(create_app())
        client.delete(f"/v1/jobs/{job.job_id}")
        resp = client.get(f"/v1/jobs/{job.job_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"
        assert resp.json()["termination_reason"] == "user_aborted"


class TestWebSocketEvents:
    def test_websocket_unknown_job_closes_4404(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        with pytest.raises(Exception):
            with client.websocket_connect("/v1/jobs/missing/events") as ws:
                ws.receive_json()

    def test_websocket_receives_initial_snapshot(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        get_job_store().clear()
        client = TestClient(create_app())
        submit = client.post("/v1/courses", json={
            "topic": "Python",
            "audience": "beginner",
            "difficulty": "beginner",
            "learning_outcomes": ["Variables"],
            "max_iterations": 1,
        }).json()
        job_id = submit["job_id"]
        with client.websocket_connect(f"/v1/jobs/{job_id}/events") as ws:
            first = ws.receive_json()
            assert first["job_id"] == job_id
            assert "status" in first


class TestEventBusIntegration:
    def test_publish_on_cancellation(self):
        from cogenai.application.jobs import (
            GenerationJob, JobEventBus, JobStatus, JobStore, get_event_bus, get_job_store,
        )
        received: list[GenerationJob] = []
        store = get_job_store()
        store.clear()
        bus = get_event_bus()
        job = store.create({"x": 1})
        bus.subscribe(job.job_id, lambda j: received.append(j))
        # Manually cancel and publish to simulate the DELETE handler.
        cancelled = store.cancel(job.job_id)
        assert cancelled is not None
        bus.publish(cancelled)
        assert len(received) == 1
        assert received[0].status == JobStatus.ABORTED