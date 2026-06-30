from __future__ import annotations

import pytest

from cogenai.application.jobs import (
    GenerationJob,
    JobEventBus,
    JobStatus,
    JobStore,
)


class TestJobEventBus:
    def test_subscribe_and_publish(self):
        bus = JobEventBus()
        received: list[GenerationJob] = []

        def cb(job: GenerationJob) -> None:
            received.append(job)

        job = GenerationJob(
            job_id="j-1", request_id="r-1", request_payload={"x": 1},
            status=JobStatus.QUEUED,
        )
        bus.subscribe("j-1", cb)
        bus.publish(job)
        assert len(received) == 1
        assert received[0].job_id == "j-1"

    def test_multiple_subscribers(self):
        bus = JobEventBus()
        a, b = [], []
        job = GenerationJob(
            job_id="j-1", request_id="r-1", request_payload={},
        )
        bus.subscribe("j-1", lambda j: a.append(j))
        bus.subscribe("j-1", lambda j: b.append(j))
        bus.publish(job)
        assert len(a) == 1
        assert len(b) == 1

    def test_unsubscribe(self):
        bus = JobEventBus()
        received: list[GenerationJob] = []

        def cb(job: GenerationJob) -> None:
            received.append(job)

        bus.subscribe("j-1", cb)
        bus.unsubscribe("j-1", cb)
        bus.publish(GenerationJob(job_id="j-1", request_id="r-1", request_payload={}))
        assert received == []

    def test_callback_exceptions_are_swallowed(self):
        bus = JobEventBus()
        a: list = []

        def bad_cb(_job):
            raise RuntimeError("boom")

        def good_cb(job):
            a.append(job)

        bus.subscribe("j-1", bad_cb)
        bus.subscribe("j-1", good_cb)
        # Should not raise, and good_cb should still receive.
        bus.publish(GenerationJob(job_id="j-1", request_id="r-1", request_payload={}))
        assert len(a) == 1

    def test_unrelated_job_does_not_invoke(self):
        bus = JobEventBus()
        received: list = []
        bus.subscribe("j-1", lambda j: received.append(j))
        bus.publish(GenerationJob(job_id="j-2", request_id="r-2", request_payload={}))
        assert received == []


class TestJobStoreCancel:
    def test_cancel_queued_job(self):
        store = JobStore()
        job = store.create({"x": 1})
        cancelled = store.cancel(job.job_id)
        assert cancelled is not None
        assert cancelled.status == JobStatus.ABORTED
        assert cancelled.termination_reason == "user_aborted"
        assert cancelled.completed_at is not None

    def test_cancel_returns_none_for_terminal(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.update(job.job_id, status=JobStatus.COMPLETED)
        assert store.cancel(job.job_id) is None

    def test_cancel_returns_none_for_unknown(self):
        store = JobStore()
        assert store.cancel("does-not-exist") is None

    def test_is_terminal_true_for_aborted(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.cancel(job.job_id)
        assert store.is_terminal(job.job_id) is True

    def test_is_terminal_false_for_queued(self):
        store = JobStore()
        job = store.create({"x": 1})
        assert store.is_terminal(job.job_id) is False