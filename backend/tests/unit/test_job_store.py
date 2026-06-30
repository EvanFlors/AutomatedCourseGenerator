from __future__ import annotations

from cogenai.application.jobs import (
    GenerationJob,
    JobStatus,
    JobStore,
    TerminationReason,
    compute_request_id,
)


class TestJobStore:
    def test_create_returns_new_job(self):
        store = JobStore()
        job = store.create({"topic": "Python", "outcomes": ["x"]})
        assert isinstance(job, GenerationJob)
        assert job.status == JobStatus.QUEUED
        assert job.request_id != ""

    def test_create_is_idempotent(self):
        store = JobStore()
        payload = {"topic": "Python", "outcomes": ["x"]}
        a = store.create(payload)
        b = store.create(payload)
        assert a.job_id == b.job_id
        assert a.request_id == b.request_id

    def test_create_with_different_payloads(self):
        store = JobStore()
        a = store.create({"topic": "Python"})
        b = store.create({"topic": "Rust"})
        assert a.job_id != b.job_id
        assert a.request_id != b.request_id

    def test_get_returns_none_for_unknown(self):
        store = JobStore()
        assert store.get("does-not-exist") is None

    def test_update_sets_fields(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.update(job.job_id, status=JobStatus.RUNNING, started_at="2026-01-01")
        fetched = store.get(job.job_id)
        assert fetched.status == JobStatus.RUNNING
        assert fetched.started_at == "2026-01-01"

    def test_update_unknown_job_raises(self):
        store = JobStore()
        import pytest
        with pytest.raises(KeyError):
            store.update("missing", status=JobStatus.FAILED)

    def test_to_dict_shape(self):
        store = JobStore()
        job = store.create({"x": 1})
        d = job.to_dict()
        assert d["job_id"] == job.job_id
        assert d["status"] == "queued"
        assert d["has_result"] is False
        assert d["error"] is None


class TestComputeRequestId:
    def test_same_payload_same_id(self):
        a = compute_request_id({"x": 1, "y": [1, 2]})
        b = compute_request_id({"y": [1, 2], "x": 1})
        assert a == b

    def test_different_payload_different_id(self):
        a = compute_request_id({"x": 1})
        b = compute_request_id({"x": 2})
        assert a != b


class TestJobStatusEnum:
    def test_status_values(self):
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.PARTIAL.value == "partial"


class TestTerminationReasonEnum:
    def test_reason_values(self):
        assert TerminationReason.QUALITY_THRESHOLD.value == "quality_threshold"
        assert TerminationReason.MAX_ITERATIONS.value == "max_iterations"
        assert TerminationReason.BUDGET_EXHAUSTED.value == "budget_exhausted"
        assert TerminationReason.USER_ABORTED.value == "user_aborted"