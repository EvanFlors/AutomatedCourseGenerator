from __future__ import annotations

import json

from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.context_synthesizer import GenerationContext
from cogenai.agents_implementations.curriculum_planner import CourseSkeleton, ModuleSpec
from cogenai.agents_implementations.evaluator import (
    EvaluationIssue, EvaluationReport, RubricScores,
)
from cogenai.agents_implementations.refiner import CourseBundle, RefinerAgent, RefinerInput
from cogenai.agents_implementations.refiners import ContextRefinerAgent
from cogenai.domain.course import Course, Module
from cogenai.domain.shared.value_objects import new_module_id
from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
from tests.unit.refinement._fixtures import FakeProvider, make_context_response


def _config() -> AgentConfig:
    return AgentConfig.default(model_name="stub-model")


def _module(title: str = "M1", order: int = 0) -> Module:
    return Module(id=new_module_id(), title=title, order=order)


def _course(modules=()) -> Course:
    return Course(
        title="Python for beginner",
        summary="A beginner course on Python covering Variables",
        learning_outcomes=("Variables",),
        source_topic="Python",
        generation_iteration=1,
        modules=tuple(modules),
    )


class SequenceProvider:
    """Provider that emits evaluator reports on successive calls."""
    def __init__(self, issues_per_call: list[list[EvaluationIssue]]):
        self._issues = list(issues_per_call)
        self._idx = 0

    def health_check(self) -> bool:
        return True

    def complete(self, request):
        if self._idx < len(self._issues):
            issues = self._issues[self._idx]
            self._idx += 1
        else:
            issues = []
        payload = {
            "rubric": {
                "accuracy": 0.7, "pedagogical_clarity": 0.7, "structure_compliance": 0.7,
                "depth_appropriateness": 0.7, "audience_alignment": 0.7,
                "consistency": 0.7, "completeness": 0.7,
            },
            "issues": [
                {
                    "id": i.id, "severity": i.severity, "scope": i.scope,
                    "target_id": i.target_id, "category": i.category,
                    "message": i.message, "suggestion": "", "auto_fixable": False,
                }
                for i in issues
            ],
        }
        return CompletionResponse(
            text=json.dumps(payload),
            model=request.model,
            usage=CompletionUsage(0, 0, 0),
            finish_reason="stop",
        )


class TestCliMetadataPropagation:
    """E2E regression: the orchestrator's metadata sync must rebuild the
    Course title/summary/audience from a refined GenerationContext so that
    successive iterations of the CLI produce visibly different output.
    """

    def _bundle(self, course=None, modules=()):
        original_ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        plan = CourseSkeleton(
            topic="Python",
            modules=(
                ModuleSpec(title="M1", summary="", order=0),
                ModuleSpec(title="M2", summary="", order=1),
            ),
            sections=(), prerequisites=(),
        )
        return CourseBundle(
            course=course or _course(modules=modules),
            context=original_ctx,
            plan=plan,
        )

    def _report(self, issue_id: str = "i-1", category: str = "audience_alignment"):
        return EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(EvaluationIssue(
                id=issue_id, severity="high", scope="course",
                target_id="course-1", category=category,
                message="audience is wrong",
            ),),
        )

    def _orchestrator(self, audience: str = "engineer", outcomes=("Variables",)):
        refiner_provider = FakeProvider(returns=make_context_response(
            audience=audience, outcomes=outcomes,
        ))
        config = _config()
        context_refiner = ContextRefinerAgent(config, refiner_provider)
        return RefinerAgent(
            config=config,
            llm_provider=SequenceProvider([[], []]),
            refiners={"context": context_refiner},
        )

    def test_title_changes_after_context_refinement(self):
        bundle = self._bundle()
        orchestrator = self._orchestrator()
        refined = orchestrator.run(RefinerInput(
            course=bundle, evaluation_report=self._report(),
        ))
        new_course = refined.revised.course
        assert "engineer" in new_course.title
        assert new_course.title != bundle.course.title
        assert new_course.version == 2
        assert new_course.generation_iteration == 2
        assert "Variables" in new_course.summary

    def test_working_bundle_is_a_course_bundle(self):
        bundle = self._bundle()
        orchestrator = self._orchestrator()
        refined = orchestrator.run(RefinerInput(
            course=bundle, evaluation_report=self._report(),
        ))
        assert isinstance(refined.revised, CourseBundle)
        assert refined.revised.context.audience == "engineer"
        assert "engineer" in refined.revised.course.title

    def test_modules_preserved_through_context_refinement(self):
        m1, m2 = _module("M1", 0), _module("M2", 1)
        bundle = self._bundle(modules=(m1, m2))
        orchestrator = self._orchestrator()
        refined = orchestrator.run(RefinerInput(
            course=bundle, evaluation_report=self._report(),
        ))
        assert len(refined.revised.course.modules) == 2
        titles = {m.title for m in refined.revised.course.modules}
        assert titles == {"M1", "M2"}

    def test_iteration_chains_via_refined_revised(self):
        """Simulates the CLI loop: each iteration feeds `refined.revised`
        back into the next orchestrator.run call. After 2 iterations the
        title must reflect the second refinement (different audience)."""
        bundle = self._bundle()
        first = self._orchestrator(audience="engineer")
        out1 = first.run(RefinerInput(
            course=bundle, evaluation_report=self._report("i-1"),
        ))
        assert "engineer" in out1.revised.course.title

        second = self._orchestrator(audience="architect")
        out2 = second.run(RefinerInput(
            course=out1.revised, evaluation_report=self._report("i-2"),
        ))
        assert "architect" in out2.revised.course.title
        assert out2.revised.course.version == 3
        assert out2.revised.course.generation_iteration == 3
