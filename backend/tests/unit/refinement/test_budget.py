from __future__ import annotations

import pytest

from cogenai.application.orchestrator.evaluator import (
    EvaluationIssue,
    EvaluationReport,
    RubricScores,
)
from cogenai.application.orchestrator.refiner import (
    BudgetExceeded,
    RefinerAgent,
    RefinerInput,
    sum_tokens,
)
from cogenai.application.orchestrator.refiners import ContextRefinerAgent
from cogenai.domain.shared.value_objects import new_course_id
from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage

from ._fixtures import FakeProvider, make_context_response
from .test_refiner_orchestrator import FakeCourse, _module


def _config():
    from cogenai.application.agents.config import AgentConfig
    return AgentConfig.default(model_name="stub-model")


class TestSumTokens:
    def test_returns_zero_for_none(self):
        assert sum_tokens(None) == 0

    def test_returns_zero_for_missing_tokens(self):
        class A:
            tokens_used = None
        assert sum_tokens(A()) == 0

    def test_sums_input_output(self):
        class A:
            tokens_used = CompletionUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        assert sum_tokens(A()) == 150

    def test_falls_back_to_input_plus_output(self):
        class A:
            tokens_used = CompletionUsage(input_tokens=200, output_tokens=0, total_tokens=0)
        assert sum_tokens(A()) == 200


class TestBudgetExhaustion:
    def test_budget_exceeded_sets_termination_reason(self):
        # Provider returns 1M tokens per call
        class _Big(FakeProvider):
            def complete(self, request):
                return CompletionResponse(
                    text=self.returns, model=request.model,
                    usage=CompletionUsage(
                        input_tokens=500_000, output_tokens=500_000,
                        total_tokens=1_000_000,
                    ),
                    finish_reason="stop",
                )
        big = _Big(returns=make_context_response())
        config = _config()
        context_refiner = ContextRefinerAgent(config, big)
        orchestrator = RefinerAgent(
            config=config, llm_provider=big,
            refiners={"context": context_refiner},
        )
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(EvaluationIssue(
                id="i-1", severity="warning", scope="course",
                target_id="course-1", category="audience_alignment",
                message="audience is wrong",
            ),),
        )
        from cogenai.application.orchestrator.context_synthesizer import GenerationContext
        from cogenai.application.orchestrator.refiner import CourseBundle
        bundle = CourseBundle(
            course=FakeCourse(modules=(_module(),)),
            context=GenerationContext(
                topic="Python", audience="beginner", difficulty="beginner",
                learning_outcomes=("Variables",),
            ),
        )
        refined = orchestrator.run(
            RefinerInput(course=bundle, evaluation_report=report),
            token_budget=10_000,
        )
        assert "budget_exhausted" in refined.refinement_notes
        # No refinement steps applied since first step tripped the cap
        assert len(refined.steps_applied) == 0

    def test_no_budget_means_unlimited(self):
        provider = FakeProvider(returns=make_context_response())
        config = _config()
        context_refiner = ContextRefinerAgent(config, provider)
        orchestrator = RefinerAgent(
            config=config, llm_provider=provider,
            refiners={"context": context_refiner},
        )
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(EvaluationIssue(
                id="i-1", severity="warning", scope="course",
                target_id="course-1", category="audience_alignment",
                message="audience is wrong",
            ),),
        )
        from cogenai.application.orchestrator.context_synthesizer import GenerationContext
        from cogenai.application.orchestrator.refiner import CourseBundle
        bundle = CourseBundle(
            course=FakeCourse(modules=(_module(),)),
            context=GenerationContext(
                topic="Python", audience="beginner", difficulty="beginner",
                learning_outcomes=("Variables",),
            ),
        )
        refined = orchestrator.run(
            RefinerInput(course=bundle, evaluation_report=report),
            token_budget=None,
        )
        assert "budget_exhausted" not in refined.refinement_notes
        assert len(refined.steps_applied) >= 1

    def test_budget_exceeded_exception_attributes(self):
        exc = BudgetExceeded(used=1000, cap=500, level="context")
        assert exc.used == 1000
        assert exc.cap == 500
        assert exc.level == "context"
        assert "budget exhausted" in str(exc)


class TestGenerationRequestTokenBudget:
    def test_token_budget_default_none(self):
        from cogenai.interfaces.dto.generation_request import GenerationRequestDTO
        r = GenerationRequestDTO(topic="x", learning_outcomes=("a",))
        assert r.token_budget is None

    def test_token_budget_validated(self):
        from cogenai.interfaces.dto.generation_request import GenerationRequestDTO
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GenerationRequestDTO(topic="x", learning_outcomes=("a",), token_budget=10)
        r = GenerationRequestDTO(topic="x", learning_outcomes=("a",), token_budget=50_000)
        assert r.token_budget == 50_000