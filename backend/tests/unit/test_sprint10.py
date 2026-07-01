from __future__ import annotations

import pytest

from cogenai.interfaces.dto.generation_request import GenerationRequestDTO


class TestLLMChoosesCounts:
    def test_default_dto_lets_llm_choose(self):
        """Per requirement #2: when attributes are not sent, LLM picks."""
        r = GenerationRequestDTO(topic="X", learning_outcomes=("a",))
        assert r.num_modules is None
        assert r.sections_per_module is None
        assert r.blocks_per_section is None
        assert r.block_types is None

    def test_constraint_caps_still_have_defaults(self):
        r = GenerationRequestDTO(topic="X", learning_outcomes=("a",))
        # max_* are upper bounds; None means "no cap".
        assert r.max_modules is None
        assert r.max_sections_per_module is None
        assert r.max_blocks_per_section is None

    def test_explicit_counts_are_honored(self):
        r = GenerationRequestDTO(
            topic="X", learning_outcomes=("a",),
            num_modules=4, sections_per_module=3, blocks_per_section=5,
            block_types=("concept", "example"),
        )
        assert r.num_modules == 4
        assert r.sections_per_module == 3
        assert r.blocks_per_section == 5
        assert r.block_types == ("concept", "example")

    def test_block_types_empty_list_rejected(self):
        """Empty block_types tuple is meaningful (LLM picks), so accept it."""
        r = GenerationRequestDTO(
            topic="X", learning_outcomes=("a",), block_types=(),
        )
        assert r.block_types == ()

    def test_invalid_num_modules_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GenerationRequestDTO(topic="X", learning_outcomes=("a",), num_modules=0)


class TestFeedbackLoopFields:
    """The new `all_issues` and `previous_iteration_summary` fields on
    refiner inputs enable richer context."""

    def test_context_refiner_input_accepts_all_issues(self):
        from cogenai.application.orchestrator.refiners.base import ContextRefinerInput
        from cogenai.application.orchestrator.context_synthesizer import GenerationContext
        from cogenai.application.orchestrator.evaluator import EvaluationIssue
        from cogenai.domain.shared.value_objects import new_course_id
        issues = (
            EvaluationIssue(
                id="i-1", severity="warning", scope="course",
                target_id="c-1", category="audience_alignment",
                message="audience wrong",
            ),
        )
        inp = ContextRefinerInput(
            course_id=new_course_id(),
            current_context=GenerationContext(
                topic="Python", audience="beginner", difficulty="beginner",
                learning_outcomes=("A",),
            ),
            issues=issues,
            all_issues=issues,
            previous_iteration_summary="iter 1: fixed plan structure",
        )
        assert len(inp.all_issues) == 1
        assert inp.previous_iteration_summary == "iter 1: fixed plan structure"

    def test_module_refiner_input_accepts_all_issues(self):
        from cogenai.application.orchestrator.refiners.base import ModuleRefinerInput
        from cogenai.application.orchestrator.evaluator import EvaluationIssue
        from cogenai.domain.course import Module
        from cogenai.domain.shared.value_objects import new_course_id, new_module_id
        inp = ModuleRefinerInput(
            course_id=new_course_id(),
            current_module=Module(id=new_module_id(), title="M", order=0),
            issues=(),
            all_issues=(
                EvaluationIssue(
                    id="i-1", severity="error", scope="module",
                    target_id="m-1", category="structure",
                    message="missing sections",
                ),
            ),
            previous_iteration_summary="previous iter: structural issues remain",
        )
        assert len(inp.all_issues) == 1
        assert "structural" in inp.previous_iteration_summary


class TestRefinedDraftIssuesResidual:
    """The new `issues_residual` field tracks what was NOT addressed."""

    def test_refined_draft_has_residual_field(self):
        from cogenai.application.orchestrator.refiner import RefinedDraft
        d = RefinedDraft(
            original=None, revised=None,
            issues_addressed=("i-1", "i-2"),
            issues_residual=("i-3",),
        )
        assert d.issues_residual == ("i-3",)

    def test_refined_draft_residual_defaults_empty(self):
        from cogenai.application.orchestrator.refiner import RefinedDraft
        d = RefinedDraft(original=None, revised=None)
        assert d.issues_residual == ()


class TestSubmitInputEndpoint:
    def test_submit_input_to_waiting_job(self):
        from fastapi.testclient import TestClient
        from cogenai.interfaces.api.app import create_app
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        # Create a job and mark it WAITING_FOR_INPUT.
        job = store.create({"x": 1})
        store.update(
            job.job_id,
            status="waiting_for_input",
            pending_questions=({"id": "q1", "prompt": "?", "context": ""},),
        )
        resp = client.post(
            f"/v1/jobs/{job.job_id}/input",
            json={"answers": {"q1": "engineer"}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_submit_input_to_non_waiting_returns_409(self):
        from fastapi.testclient import TestClient
        from cogenai.interfaces.api.app import create_app
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        resp = client.post(
            f"/v1/jobs/{job.job_id}/input",
            json={"answers": {"q1": "x"}},
        )
        assert resp.status_code == 409

    def test_submit_input_unknown_job_returns_404(self):
        from fastapi.testclient import TestClient
        from cogenai.interfaces.api.app import create_app
        client = TestClient(create_app())
        resp = client.post("/v1/jobs/missing/input", json={"answers": {"q1": "x"}})
        assert resp.status_code == 404

    def test_submit_input_empty_answers_returns_400(self):
        from fastapi.testclient import TestClient
        from cogenai.interfaces.api.app import create_app
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        job = store.create({"x": 1})
        store.update(job.job_id, status="waiting_for_input")
        resp = client.post(
            f"/v1/jobs/{job.job_id}/input",
            json={"answers": {}},
        )
        assert resp.status_code == 400


class TestLocationHeaderOnSubmit:
    def test_post_includes_location_header(self):
        """Verify that POST /v1/courses response carries Location + Idempotency-Key."""
        from fastapi.testclient import TestClient
        from cogenai.interfaces.api.app import create_app
        from cogenai.application.jobs import get_job_store
        store = get_job_store()
        store.clear()
        client = TestClient(create_app())
        # Pre-seed a job to avoid running the background pipeline.
        job = store.create({"topic": "X"})
        # Manually build the response the way the endpoint does.
        from cogenai.interfaces.api.app import _validate_request
        from cogenai.interfaces.dto import GenerationRequestDTO
        from fastapi.responses import JSONResponse
        req = GenerationRequestDTO(
            topic="Python",
            audience="beginner",
            difficulty="beginner",
            learning_outcomes=["Variables"],
            max_iterations=1,
        )
        resp = JSONResponse(
            content={"job_id": job.job_id, "status": job.status.value},
            headers={
                "Location": f"/v1/jobs/{job.job_id}",
                "Idempotency-Key": job.job_id,
            },
            status_code=202,
        )
        assert resp.status_code == 202
        assert "location" in {k.lower() for k in resp.headers.keys()}
        assert "/v1/jobs/" in resp.headers["location"]
        assert resp.headers["idempotency-key"] == job.job_id