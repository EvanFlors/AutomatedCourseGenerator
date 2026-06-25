from __future__ import annotations

import os
import tempfile

import pytest

from cogenai.bootstrap.jobs import (
    GenerationJob,
    JobStatus,
    SqliteJobStore,
    TerminationReason,
)


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestSqliteJobStore:
    def test_create_and_get(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        job = store.create({"topic": "Python"})
        assert job.status == JobStatus.QUEUED
        fetched = store.get(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id
        assert fetched.request_payload == {"topic": "Python"}

    def test_create_is_idempotent(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        a = store.create({"topic": "Python"})
        b = store.create({"topic": "Python"})
        assert a.job_id == b.job_id

    def test_persistence_across_instances(self, tmp_db):
        store1 = SqliteJobStore(tmp_db)
        job = store1.create({"topic": "Python"})
        store1.update(job.job_id, status=JobStatus.RUNNING, started_at="2026-01-01")
        # New instance reads the same data from disk
        store2 = SqliteJobStore(tmp_db)
        fetched = store2.get(job.job_id)
        assert fetched is not None
        assert fetched.status == JobStatus.RUNNING
        assert fetched.started_at == "2026-01-01"

    def test_update_unknown_job_raises(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        import pytest
        with pytest.raises(KeyError):
            store.update("missing-id", status=JobStatus.FAILED)

    def test_update_with_invalid_field_raises(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        job = store.create({"x": 1})
        import pytest
        with pytest.raises(AttributeError):
            store.update(job.job_id, nonexistent_field="oops")

    def test_update_persists_result(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        job = store.create({"x": 1})
        store.update(
            job.job_id,
            status=JobStatus.COMPLETED,
            termination_reason=TerminationReason.QUALITY_THRESHOLD.value,
            result={"course": {"title": "Python"}},
        )
        fetched = store.get(job.job_id)
        assert fetched is not None
        assert fetched.status == JobStatus.COMPLETED
        assert fetched.result == {"course": {"title": "Python"}}

    def test_list_ids(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        store.create({"a": 1})
        store.create({"b": 2})
        ids = store.list_ids()
        assert len(ids) == 2

    def test_clear(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        store.create({"x": 1})
        store.clear()
        assert store.list_ids() == []

    def test_get_missing_returns_none(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        assert store.get("missing") is None

    def test_payload_round_trip_complex(self, tmp_db):
        store = SqliteJobStore(tmp_db)
        payload = {
            "topic": "Python",
            "learning_outcomes": ["a", "b"],
            "nested": {"k": ["v1", "v2"]},
        }
        job = store.create(payload)
        fetched = store.get(job.job_id)
        assert fetched is not None
        assert fetched.request_payload == payload