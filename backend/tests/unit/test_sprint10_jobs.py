from __future__ import annotations

import pytest

from cogenai.application.jobs import (
    GenerationJob,
    JobStatus,
    JobStore,
    SqliteJobStore,
)


class TestGenerationJobFields:
    def test_default_pending_questions_empty(self):
        job = GenerationJob(job_id="j", request_id="r", request_payload={})
        assert job.pending_questions == ()
        assert job.human_answers == {}
        assert job.last_thinking == ""

    def test_to_dict_includes_new_fields(self):
        job = GenerationJob(
            job_id="j", request_id="r", request_payload={},
            pending_questions=({"id": "q1", "prompt": "?", "context": ""},),
            human_answers={"q1": "yes"},
            last_thinking="thought process",
        )
        d = job.to_dict()
        assert d["pending_questions"] == [{"id": "q1", "prompt": "?", "context": ""}]
        assert d["human_answers"] == {"q1": "yes"}
        assert d["last_thinking"] == "thought process"


class TestJobStoreSubmitAnswer:
    def test_submit_answer_records_answers(self):
        store = JobStore()
        job = store.create({"x": 1})
        # Manually mark WAITING_FOR_INPUT.
        store.update(
            job.job_id,
            status=JobStatus.WAITING_FOR_INPUT,
            pending_questions=({"id": "q1", "prompt": "Audience?", "context": ""},),
        )
        updated = store.submit_answer(job.job_id, {"q1": "engineer"})
        assert updated is not None
        assert updated.human_answers == {"q1": "engineer"}

    def test_submit_answer_returns_to_running_when_no_pending(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.update(
            job.job_id,
            status=JobStatus.WAITING_FOR_INPUT,
            pending_questions=({"id": "q1", "prompt": "?", "context": ""},),
        )
        updated = store.submit_answer(job.job_id, {"q1": "answer"})
        assert updated.status == JobStatus.RUNNING
        assert updated.pending_questions == ()

    def test_submit_answer_keeps_waiting_when_pending_remains(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.update(
            job.job_id,
            status=JobStatus.WAITING_FOR_INPUT,
            pending_questions=(
                {"id": "q1", "prompt": "A?", "context": ""},
                {"id": "q2", "prompt": "B?", "context": ""},
            ),
        )
        updated = store.submit_answer(job.job_id, {"q1": "answer1"})
        assert updated.status == JobStatus.WAITING_FOR_INPUT
        assert len(updated.pending_questions) == 1
        assert updated.pending_questions[0]["id"] == "q2"

    def test_submit_answer_rejects_non_waiting(self):
        store = JobStore()
        job = store.create({"x": 1})
        result = store.submit_answer(job.job_id, {"q1": "answer"})
        assert result is None

    def test_submit_answer_unknown_job_returns_none(self):
        store = JobStore()
        assert store.submit_answer("missing", {}) is None


class TestSqliteSubmitAnswer:
    def test_submit_answer_round_trip(self, tmp_path):
        db = tmp_path / "test.db"
        store = SqliteJobStore(str(db))
        job = store.create({"x": 1})
        store.update(
            job.job_id,
            status=JobStatus.WAITING_FOR_INPUT,
            pending_questions=({"id": "q1", "prompt": "?", "context": ""},),
        )
        updated = store.submit_answer(job.job_id, {"q1": "answer"})
        assert updated is not None
        # Reload from the same SQLite file.
        store2 = SqliteJobStore(str(db))
        fresh = store2.get(job.job_id)
        assert fresh is not None
        assert fresh.human_answers == {"q1": "answer"}
        assert fresh.status == JobStatus.RUNNING


class TestWaitingForInputLifecycle:
    """End-to-end: WAITING_FOR_INPUT is non-terminal but cancelable."""

    def test_waiting_for_input_is_not_terminal(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.update(job.job_id, status=JobStatus.WAITING_FOR_INPUT)
        assert store.is_terminal(job.job_id) is False

    def test_waiting_for_input_is_not_cancelled(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.update(job.job_id, status=JobStatus.WAITING_FOR_INPUT)
        assert store.is_cancelled(job.job_id) is False

    def test_cancel_from_waiting_for_input(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.update(job.job_id, status=JobStatus.WAITING_FOR_INPUT)
        cancelled = store.cancel(job.job_id)
        assert cancelled is not None
        assert cancelled.status == JobStatus.ABORTED


class TestDefaultStoreFromEnv:
    def test_default_in_memory(self, monkeypatch):
        from cogenai.application.jobs import _default_store, JobStore
        monkeypatch.delenv("COGENAI_JOB_STORE", raising=False)
        store = _default_store()
        assert isinstance(store, JobStore)

    def test_env_overrides_to_sqlite(self, monkeypatch, tmp_path):
        from cogenai.application.jobs import _default_store, SqliteJobStore
        monkeypatch.setenv("COGENAI_JOB_STORE", f"sqlite:{tmp_path / 'env.db'}")
        store = _default_store()
        assert isinstance(store, SqliteJobStore)

    def test_invalid_env_raises(self, monkeypatch):
        from cogenai.application.jobs import _default_store
        monkeypatch.setenv("COGENAI_JOB_STORE", "weird-backend")
        with pytest.raises(ValueError):
            _default_store()