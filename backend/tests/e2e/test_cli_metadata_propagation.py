from __future__ import annotations

import json

from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.context_synthesizer import GenerationContext
from cogenai.application.orchestrator.curriculum_planner import CourseSkeleton, ModuleSpec
from cogenai.application.orchestrator.evaluator import (
    EvaluationIssue, EvaluationReport, RubricScores,
)
from cogenai.application.orchestrator.refiner import CourseBundle, RefinerAgent, RefinerInput
from cogenai.application.orchestrator.refiners import (
    ContextRefinerAgent,
    MetadataRefinerAgent,
)
from cogenai.domain.course import Course, Module
from cogenai.domain.shared.value_objects import new_module_id
from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
from tests.unit.refinement._fixtures import (
    FakeProvider, make_context_response, make_metadata_response,
)


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

    def test_metadata_refiner_updates_tags_and_language(self):
        """E2E: a course-scope issue with category='metadata' routes
        through the IssueAnalyzer to the new metadata_refiner, which
        updates Course.tags and Course.language on the bundle."""
        bundle = self._bundle()
        bundle.course = Course(
            id=bundle.course.id,
            title=bundle.course.title,
            summary=bundle.course.summary,
            language="en",
            audience=bundle.course.audience,
            difficulty=bundle.course.difficulty,
            learning_outcomes=bundle.course.learning_outcomes,
            modules=bundle.course.modules,
            tags=("old", "stale"),
            version=bundle.course.version,
            generation_iteration=bundle.course.generation_iteration,
            source_topic=bundle.course.source_topic,
        )
        meta_provider = FakeProvider(returns=make_metadata_response(
            tags=["python", "beginner", "tutorial", "fundamentals"],
            language="es",
        ))
        config = _config()
        meta_refiner = MetadataRefinerAgent(config, meta_provider)
        orchestrator = RefinerAgent(
            config=config,
            llm_provider=SequenceProvider([[], []]),
            refiners={"metadata": meta_refiner},
        )
        report = EvaluationReport(
            overall_score=0.4, passed=False, rubric=RubricScores(),
            issues=(EvaluationIssue(
                id="m-1", severity="medium", scope="course",
                target_id=str(bundle.course.id),
                category="metadata",
                message="tags are stale and language is wrong",
            ),),
        )
        refined = orchestrator.run(RefinerInput(
            course=bundle, evaluation_report=report,
        ))
        assert "python" in refined.revised.course.tags
        assert "beginner" in refined.revised.course.tags
        assert refined.revised.course.language == "es"
        assert "old" not in refined.revised.course.tags
        assert refined.revised.course.version > bundle.course.version

    def test_metadata_refiner_computes_duration_deterministically(self):
        """Duration comes from the course structure, not the LLM. The
        refiner just propagates the computed value into the Course."""
        from cogenai.application.orchestrator.refiners import (
            _compute_duration_minutes,
        )
        bundle = self._bundle(modules=(_module(),))
        m = bundle.course.modules[0]
        from cogenai.domain.shared.value_objects import new_section_id
        from cogenai.domain.course import ContentBlock, Section
        blocks = (
            ContentBlock(id=bundle.course.id, type="concept", order=0, estimated_time_minutes=5),
            ContentBlock(id=bundle.course.id, type="exercise", order=1, estimated_time_minutes=10),
        )
        section = Section(
            id=new_section_id(), title="S", order=0,
            blocks=blocks, learning_objectives=["LO"],
        )
        new_module = Module(
            id=m.id, title=m.title, order=m.order,
            sections=(section,),
        )
        bundle.course = Course(
            id=bundle.course.id,
            title=bundle.course.title,
            summary=bundle.course.summary,
            language=bundle.course.language,
            audience=bundle.course.audience,
            difficulty=bundle.course.difficulty,
            learning_outcomes=bundle.course.learning_outcomes,
            modules=(new_module,),
            version=bundle.course.version,
            generation_iteration=bundle.course.generation_iteration,
            source_topic=bundle.course.source_topic,
        )
        assert _compute_duration_minutes(bundle) == 15
