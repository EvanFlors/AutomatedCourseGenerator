from __future__ import annotations

import pytest

from cogenai.application.jobs import GenerationJob, JobStore, SqliteJobStore
from cogenai.interfaces.api.app import create_app
from cogenai.interfaces.dto.generation_request import GenerationRequestDTO


class TestDecisionLogField:
    def test_default_empty_decision_log(self):
        job = GenerationJob(job_id="j", request_id="r", request_payload={})
        assert job.decision_log == ()

    def test_to_dict_includes_decision_log(self):
        job = GenerationJob(
            job_id="j", request_id="r", request_payload={},
            decision_log=({"iteration": 1, "think": "fix plan"},),
        )
        d = job.to_dict()
        assert d["decision_log"] == [{"iteration": 1, "think": "fix plan"}]


class TestRecordDecisionInMemory:
    def test_record_decision_appends_to_log(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.record_decision(job.job_id, {
            "iteration": 1, "think": "first think", "actions": [],
        })
        refreshed = store.get(job.job_id)
        assert len(refreshed.decision_log) == 1
        assert refreshed.decision_log[0]["think"] == "first think"
        assert refreshed.last_thinking == "first think"

    def test_record_decision_updates_thinking(self):
        store = JobStore()
        job = store.create({"x": 1})
        store.record_decision(job.job_id, {
            "iteration": 2, "think": "second think", "actions": [],
        })
        refreshed = store.get(job.job_id)
        assert refreshed.last_thinking == "second think"
        assert len(refreshed.decision_log) == 1

    def test_record_decision_unknown_returns_none(self):
        store = JobStore()
        assert store.record_decision("missing", {}) is None

    def test_multiple_decisions_accumulate(self):
        store = JobStore()
        job = store.create({"x": 1})
        for i in range(3):
            store.record_decision(job.job_id, {
                "iteration": i + 1, "think": f"think {i}",
            })
        refreshed = store.get(job.job_id)
        assert len(refreshed.decision_log) == 3
        # Last think wins.
        assert refreshed.last_thinking == "think 2"


class TestRecordDecisionSqlite:
    def test_decision_log_round_trip(self, tmp_path):
        db = tmp_path / "audit.db"
        store = SqliteJobStore(str(db))
        job = store.create({"x": 1})
        store.record_decision(job.job_id, {
            "iteration": 1, "think": "first", "actions": ["context"],
        })
        store.record_decision(job.job_id, {
            "iteration": 2, "think": "second", "actions": [],
        })
        store2 = SqliteJobStore(str(db))
        fresh = store2.get(job.job_id)
        assert len(fresh.decision_log) == 2
        assert fresh.last_thinking == "second"


class TestGetQuestionsEndpoint:
    def test_returns_questions_for_waiting_job(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        store.update(
            job.job_id,
            status="waiting_for_input",
            pending_questions=(
                {"id": "q1", "prompt": "Audience?", "context": "ambiguous"},
            ),
            human_answers={"q1_partial": "engine"},
        )
        resp = client.get(f"/v1/jobs/{job.job_id}/questions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == job.job_id
        assert body["status"] == "waiting_for_input"
        assert len(body["questions"]) == 1
        assert body["questions"][0]["id"] == "q1"
        assert body["human_answers"]["q1_partial"] == "engine"

    def test_returns_404_for_unknown_job(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        resp = client.get("/v1/jobs/missing/questions")
        assert resp.status_code == 404

    def test_returns_empty_questions_for_running_job(self):
        from fastapi.testclient import TestClient
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        resp = client.get(f"/v1/jobs/{job.job_id}/questions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["questions"] == []


class TestUseLLMOrchestratorFlag:
    def test_flag_is_accepted_in_query(self):
        """Verify the query param is wired into the endpoint without errors.

        We don't actually run the LLM orchestrator (the test would hang on
        the real LLM). Instead, we verify the flag is accepted and the
        request goes through validation by inspecting the OpenAPI schema.
        """
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        schema = client.get("/openapi.json").json()
        post_op = schema["paths"]["/v1/courses"]["post"]
        params = post_op.get("parameters", [])
        flag = next(
            (p for p in params if p.get("name") == "use_llm_orchestrator"),
            None,
        )
        assert flag is not None
        assert flag["in"] == "query"
        assert flag["schema"]["type"] == "boolean"

    def test_default_does_not_use_llm_orchestrator(self):
        from fastapi.testclient import TestClient
        client = TestClient(create_app())
        schema = client.get("/openapi.json").json()
        post_op = schema["paths"]["/v1/courses"]["post"]
        params = post_op.get("parameters", [])
        flag = next(
            (p for p in params if p.get("name") == "use_llm_orchestrator"),
            None,
        )
        assert flag["schema"]["default"] is False


class TestDecisionLogSchemaConsistency:
    """The decision_log entry shape should be a JSON-serializable dict."""

    def test_decision_log_entry_round_trips_through_json(self):
        store = JobStore()
        job = store.create({"x": 1})
        entry = {
            "iteration": 1,
            "think": "chain of thought summary",
            "actions": [
                {"level": "context", "reason": "fix audience"},
                {"level": "plan", "reason": "restructure modules"},
            ],
            "questions": [],
            "terminate": False,
            "termination_reason": None,
        }
        store.record_decision(job.job_id, entry)
        # Reload and verify shape preserved.
        refreshed = store.get(job.job_id)
        assert refreshed.decision_log[0] == entry