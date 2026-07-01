from __future__ import annotations

import pytest

from cogenai.application.jobs import GenerationJob, JobStatus, JobStore, SqliteJobStore
from cogenai.application.webhooks import WebhookRegistry, get_webhook_registry
from cogenai.interfaces.api.app import create_app, rehydrate_waiting_jobs


class TestDecisionsEndpoint:
    def test_returns_decision_log(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        store.record_decision(job.job_id, {
            "iteration": 1, "think": "first", "actions": [],
        })
        store.record_decision(job.job_id, {
            "iteration": 2, "think": "second", "actions": [{"level": "plan"}],
        })
        resp = client.get(f"/v1/jobs/{job.job_id}/decisions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["decision_log"]) == 2
        assert body["last_thinking"] == "second"

    def test_404_for_unknown(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.get("/v1/jobs/missing/decisions")
        assert resp.status_code == 404

    def test_empty_decision_log(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        resp = client.get(f"/v1/jobs/{job.job_id}/decisions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision_log"] == []


class TestWebhookRegistry:
    def test_subscribe_and_unsubscribe(self):
        reg = WebhookRegistry()
        reg.subscribe("job-1", "http://localhost:8000/hook")
        assert "http://localhost:8000/hook" in reg.subscribers_for("job-1")
        reg.unsubscribe("job-1", "http://localhost:8000/hook")
        assert reg.subscribers_for("job-1") == set()

    def test_subscribe_rejects_unsafe_url(self):
        reg = WebhookRegistry()
        with pytest.raises(ValueError):
            reg.subscribe("job-1", "ftp://example.com/hook")
        with pytest.raises(ValueError):
            reg.subscribe("job-1", "http://example.com/hook")  # not localhost/private

    def test_subscribe_allows_localhost_and_private(self):
        reg = WebhookRegistry()
        for url in (
            "http://localhost:8000/hook",
            "http://127.0.0.1:9000/hook",
            "http://10.0.0.5/hook",
            "http://192.168.1.10/hook",
            "http://172.16.5.5/hook",
        ):
            reg.subscribe("j-1", url)
        assert len(reg.subscribers_for("j-1")) == 5

    def test_clear(self):
        reg = WebhookRegistry()
        reg.subscribe("j-1", "http://localhost:8000/hook")
        reg.clear()
        assert reg.subscribers_for("j-1") == set()

    def test_notify_records_attempts_and_successes(self):
        reg = WebhookRegistry()
        # Stub server via a local HTTP request we know will fail.
        reg.subscribe("j-1", "http://localhost:1/nope")  # port 1 = unreachable
        results = reg.notify("j-1", {"event": "test"})
        assert len(results) == 1
        url, success = results[0]
        assert success is False
        assert reg.delivery_attempts[url] == 1
        assert reg.delivery_successes[url] == 0


class TestWebhookEndpoints:
    def test_subscribe_endpoint(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        from cogenai.application.webhooks import get_webhook_registry
        store = get_job_store()
        store.clear()
        get_webhook_registry().clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        resp = client.post(
            f"/v1/jobs/{job.job_id}/webhooks",
            json={"url": "http://localhost:8000/hook"},
        )
        assert resp.status_code == 200
        assert resp.json()["subscribed"] is True

    def test_subscribe_404_for_unknown_job(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.post(
            "/v1/jobs/missing/webhooks",
            json={"url": "http://localhost:8000/hook"},
        )
        assert resp.status_code == 404

    def test_subscribe_400_for_missing_url(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        resp = client.post(
            f"/v1/jobs/{job.job_id}/webhooks",
            json={},
        )
        assert resp.status_code == 400

    def test_subscribe_400_for_unsafe_url(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        resp = client.post(
            f"/v1/jobs/{job.job_id}/webhooks",
            json={"url": "http://example.com/hook"},
        )
        assert resp.status_code == 400

    def test_unsubscribe_endpoint(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        from cogenai.application.webhooks import get_webhook_registry
        store = get_job_store()
        store.clear()
        get_webhook_registry().clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        client.post(
            f"/v1/jobs/{job.job_id}/webhooks",
            json={"url": "http://localhost:8000/hook"},
        )
        resp = client.delete(
            f"/v1/jobs/{job.job_id}/webhooks?url=http://localhost:8000/hook",
        )
        assert resp.status_code == 200
        assert resp.json()["subscribed"] is False


class TestRehydrateWaitingJobs:
    def test_rehydrate_publishes_waiting_jobs(self):
        from cogenai.application.jobs import JobEventBus
        store = JobStore()
        bus = JobEventBus()
        received: list = []

        job = store.create({"x": 1})
        store.update(job.job_id, status=JobStatus.WAITING_FOR_INPUT)
        # Now subscribe (simulating a fresh WebSocket client connecting
        # right after server restart, before rehydration runs).
        def _on_event(published_job):
            received.append(published_job)
        bus.subscribe(job.job_id, _on_event)

        count = rehydrate_waiting_jobs(store, bus)
        assert count == 1
        assert len(received) == 1
        assert received[0].job_id == job.job_id
        status_value = (
            received[0].status.value
            if hasattr(received[0].status, "value")
            else str(received[0].status)
        )
        assert status_value == "waiting_for_input"

    def test_rehydrate_ignores_running_and_terminal(self):
        from cogenai.application.jobs import JobEventBus
        store = JobStore()
        bus = JobEventBus()

        queued = store.create({"x": 1})  # status = queued
        completed = store.create({"x": 2})
        store.update(completed.job_id, status=JobStatus.COMPLETED)
        waiting = store.create({"x": 3})
        store.update(waiting.job_id, status=JobStatus.WAITING_FOR_INPUT)

        count = rehydrate_waiting_jobs(store, bus)
        assert count == 1
        # The bus publishes the waiting job, but not queued or completed.
        qv = queued.status.value if hasattr(queued.status, "value") else str(queued.status)
        cv = completed.status.value if hasattr(completed.status, "value") else str(completed.status)
        assert qv == "queued"
        assert cv == "completed"


class TestPerJobMetrics:
    def test_record_job_submitted_for(self):
        from cogenai.application.metrics import (
            get_metrics_registry,
            record_job_submitted_for,
        )
        get_metrics_registry().reset()
        record_job_submitted_for("j-1")
        record_job_submitted_for("j-1")
        record_job_submitted_for("j-2")
        assert (
            get_metrics_registry().get_counter(
                "cogenai_job_submissions_total", job_id="j-1",
            )
            == 2.0
        )
        assert (
            get_metrics_registry().get_counter(
                "cogenai_job_submissions_total", job_id="j-2",
            )
            == 1.0
        )

    def test_record_tokens_used_for(self):
        from cogenai.application.metrics import (
            get_metrics_registry,
            record_tokens_used_for,
        )
        get_metrics_registry().reset()
        record_tokens_used_for("j-1", 100)
        record_tokens_used_for("j-1", 250)
        record_tokens_used_for("j-2", 50)
        record_tokens_used_for("j-3", 0)  # ignored
        assert (
            get_metrics_registry().get_counter(
                "cogenai_job_tokens_used_total", job_id="j-1",
            )
            == 350.0
        )
        assert (
            get_metrics_registry().get_counter(
                "cogenai_job_tokens_used_total", job_id="j-2",
            )
            == 50.0
        )
        assert (
            get_metrics_registry().get_counter(
                "cogenai_job_tokens_used_total", job_id="j-3",
            )
            == 0.0
        )