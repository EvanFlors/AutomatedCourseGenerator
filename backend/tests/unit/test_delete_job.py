from __future__ import annotations

import os
import tempfile

import pytest

from cogenai.bootstrap.app import create_app


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


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


class TestDeleteJob:
    def test_delete_unknown_job_returns_404(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.delete("/v1/jobs/missing")
        assert resp.status_code == 404

    def test_delete_terminal_job_returns_409(self):
        from fastapi.testclient import TestClient
        from cogenai.bootstrap.jobs import JobStatus, get_job_store
        store = get_job_store()
        store.clear()
        # Insert a manually-completed job.
        job = store.create({"x": 1})
        store.update(job.job_id, status=JobStatus.COMPLETED)
        client = TestClient(create_app())
        resp = client.delete(f"/v1/jobs/{job.job_id}")
        assert resp.status_code == 409

    def test_delete_aborted_job_returns_409(self):
        from fastapi.testclient import TestClient
        from cogenai.bootstrap.jobs import JobStatus, get_job_store
        store = get_job_store()
        store.clear()
        job = store.create({"x": 1})
        store.update(job.job_id, status=JobStatus.ABORTED)
        client = TestClient(create_app())
        resp = client.delete(f"/v1/jobs/{job.job_id}")
        assert resp.status_code == 409

    def test_delete_queued_job_marks_aborted(self):
        from fastapi.testclient import TestClient
        from cogenai.bootstrap.jobs import JobStatus, get_job_store
        store = get_job_store()
        store.clear()
        job = store.create({"x": 1})
        client = TestClient(create_app())
        resp = client.delete(f"/v1/jobs/{job.job_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "aborted"
        fetched = store.get(job.job_id)
        assert fetched.status == JobStatus.ABORTED
        assert fetched.termination_reason == "user_aborted"

    def test_get_after_delete_shows_aborted(self):
        from fastapi.testclient import TestClient
        from cogenai.bootstrap.jobs import get_job_store
        store = get_job_store()
        store.clear()
        job = store.create({"x": 1})
        client = TestClient(create_app())
        client.delete(f"/v1/jobs/{job.job_id}")
        resp = client.get(f"/v1/jobs/{job.job_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"


class TestJobStoreFactory:
    def test_make_memory(self):
        from cogenai.bootstrap.jobs import JobStore, make_job_store
        store = make_job_store("memory")
        assert isinstance(store, JobStore)

    def test_make_sqlite(self, tmp_db):
        from cogenai.bootstrap.jobs import SqliteJobStore, make_job_store
        store = make_job_store("sqlite", db_path=tmp_db)
        assert isinstance(store, SqliteJobStore)

    def test_make_unknown_raises(self):
        from cogenai.bootstrap.jobs import make_job_store
        import pytest
        with pytest.raises(ValueError):
            make_job_store("redis")

    def test_make_sqlite_without_path_raises(self):
        from cogenai.bootstrap.jobs import make_job_store
        import pytest
        with pytest.raises(ValueError):
            make_job_store("sqlite")