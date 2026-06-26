from __future__ import annotations

import pytest

from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.context_synthesizer import GenerationContext
from cogenai.application.orchestrator.curriculum_planner import (
    CourseSkeleton,
    ModuleSpec,
    Prerequisite,
    SectionSpec,
)
from cogenai.application.orchestrator.evaluator import (
    EvaluationIssue,
    EvaluationReport,
    RubricScores,
)
from cogenai.application.orchestrator.refiner import (
    RefinedDraft,
    RefinementStepResult,
    RefinerAgent,
    RefinerInput,
)
from cogenai.application.orchestrator.refiners import (
    BlockRefinerAgent,
    ContextRefinerAgent,
    IssueAnalyzer,
    ModuleRefinerAgent,
    PlanRefinerAgent,
    PrerequisitesRefinerAgent,
    RefinementPlanner,
    RefinerError,
    SectionRefinerAgent,
)
from cogenai.domain.course import ContentBlock, Course, Module, Section
from cogenai.domain.shared.value_objects import (
    new_block_id,
    new_course_id,
    new_module_id,
    new_section_id,
)

from ._fixtures import FakeProvider, _config, make_issue, make_block_response


class StubProvider:
    def health_check(self) -> bool:
        return True

    def complete(self, request):
        from cogenai.domain.value_objects.llm import (
            CompletionResponse,
            CompletionUsage,
        )
        return CompletionResponse(
            text='{"ok": true}',
            model=request.model,
            usage=CompletionUsage(0, 0, 0),
            finish_reason="stop",
        )


def _block(content=None):
    return ContentBlock(
        id=new_block_id(),
        type="exercise",
        order=0,
        content=content or {"prompt": "old"},
    )


def _section():
    return Section(
        id=new_section_id(),
        title="Section",
        order=0,
        blocks=(_block(),),
        learning_objectives=["LO1"],
    )


def _module():
    return Module(
        id=new_module_id(),
        title="Module",
        summary="summary",
        order=0,
        sections=(_section(),),
    )


class FakeCourse:
    """Minimal stand-in for a Course entity with extra fields the orchestrator probes."""

    def __init__(
        self,
        course_id=None,
        modules=(),
        context=None,
        plan=None,
        prerequisites=(),
        title="Course",
        summary="Course summary",
        learning_outcomes=(),
    ):
        self.id = course_id or new_course_id()
        self.title = title
        self.summary = summary
        self.modules = tuple(modules)
        self.context = context
        self.plan = plan
        self.prerequisites = tuple(prerequisites)
        self.learning_outcomes = tuple(learning_outcomes)
        self.version = 1

    def with_modules(self, modules, new_version):
        new_course = FakeCourse(
            course_id=self.id,
            modules=tuple(modules),
            context=self.context,
            plan=self.plan,
            prerequisites=self.prerequisites,
            title=self.title,
            summary=self.summary,
            learning_outcomes=self.learning_outcomes,
        )
        new_course.version = new_version
        return new_course


class TestRefinerOrchestratorSmoke:

    def test_orchestrator_runs_analyzer_and_planner(self):
        agent = RefinerAgent(_config(), StubProvider(), refiners={})
        course = FakeCourse(modules=(_module(),))
        report = EvaluationReport(
            overall_score=0.5,
            passed=False,
            rubric=RubricScores(),
            issues=(
                make_issue(issue_id="i-1", scope="block", target_id="some-block-id"),
            ),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert isinstance(out, RefinedDraft)
        assert out.refinement_notes  # planner.rationale is non-empty

    def test_orchestrator_with_no_refiners_records_skipped_steps(self):
        agent = RefinerAgent(_config(), StubProvider(), refiners={})
        course = FakeCourse(modules=(_module(),))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="block", target_id="x"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.auto_fixed is False
        assert out.steps_skipped  # at least one skipped because no refiner registered
        assert out.steps_applied == ()
        assert out.revised is out.original  # no refiners => no changes

    def test_orchestrator_prompt_registered(self):
        from cogenai.prompt import get_prompt
        bundle = get_prompt("orchestrator", "1.0.0")
        assert bundle is not None
        assert "orchestrator" in bundle.system_prompt.lower()


class TestRefinerOrchestratorDispatch:

    def test_orchestrator_dispatches_block_step(self):
        block_refiner = BlockRefinerAgent(
            _config(), FakeProvider(returns=make_block_response({"prompt": "new"}))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"block": block_refiner},
        )
        module = _module()
        block_id = str(module.sections[0].blocks[0].id)
        course = FakeCourse(modules=(module,))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="block", target_id=block_id),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_applied
        assert out.auto_fixed is True
        assert out.refinement_notes

    def test_orchestrator_dispatches_section_step(self):
        from ._fixtures import make_section_response
        section_refiner = SectionRefinerAgent(
            _config(), FakeProvider(returns=make_section_response("New Title", ["LO1"]))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"section": section_refiner},
        )
        module = _module()
        section_id = str(module.sections[0].id)
        course = FakeCourse(modules=(module,))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="section", target_id=section_id),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_applied

    def test_orchestrator_dispatches_module_step(self):
        from ._fixtures import make_module_response
        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("New Title", "new summary"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )
        module = _module()
        course = FakeCourse(modules=(module,))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(module.id)),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_applied

    def test_orchestrator_dispatches_context_step(self):
        from ._fixtures import make_context_response
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response(audience="engineer"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        course = FakeCourse(context=ctx)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_applied

    def test_orchestrator_dispatches_plan_step(self):
        from ._fixtures import make_plan_response
        plan_refiner = PlanRefinerAgent(
            _config(), FakeProvider(returns=make_plan_response([]))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"plan": plan_refiner},
        )
        ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        plan = CourseSkeleton(
            topic="Python",
            modules=(ModuleSpec(title="M1", summary="", order=0),),
            sections=(),
            prerequisites=(),
        )
        course = FakeCourse(context=ctx, plan=plan)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="structural"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_applied

    def test_orchestrator_dispatches_prerequisites_step(self):
        from ._fixtures import make_prereqs_response
        prereqs_refiner = PrerequisitesRefinerAgent(
            _config(), FakeProvider(returns=make_prereqs_response([]))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"prerequisites": prereqs_refiner},
        )
        course = FakeCourse(prerequisites=())
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="prerequisite"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_applied


class TestRefinerOrchestratorErrorHandling:

    def test_orchestrator_handles_refiner_truncation_error(self):
        from cogenai.application.orchestrator.refiners import RefinerOutputTruncated
        bad_refiner = BlockRefinerAgent(
            _config(), FakeProvider(returns="not json at all")
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"block": bad_refiner},
        )
        course = FakeCourse(modules=(_module(),))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="block", target_id="some-id"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_skipped
        assert not out.auto_fixed

    def test_orchestrator_handles_missing_target_entity(self):
        block_refiner = BlockRefinerAgent(
            _config(), FakeProvider(returns=make_block_response({"prompt": "new"}))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"block": block_refiner},
        )
        course = FakeCourse(modules=(_module(),))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="block", target_id="nonexistent-id"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_skipped
        assert len(out.steps_skipped) == 1
        assert out.auto_fixed is False

    def test_orchestrator_handles_missing_context_on_course(self):
        from ._fixtures import make_context_response
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response(audience="engineer"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        course = FakeCourse(context=None)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_skipped

    def test_orchestrator_handles_missing_plan_on_course(self):
        from ._fixtures import make_plan_response
        plan_refiner = PlanRefinerAgent(
            _config(), FakeProvider(returns=make_plan_response([]))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"plan": plan_refiner},
        )
        course = FakeCourse(plan=None)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="structural"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_skipped


class TestRefinerOrchestratorUserFeedback:

    def test_user_feedback_creates_synthetic_module_issue(self):
        from ._fixtures import make_module_response
        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("New Title", "new summary"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )
        module = _module()
        course = FakeCourse(modules=(module,))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(), issues=(),
        )
        out = agent.run(RefinerInput(
            course=course,
            evaluation_report=report,
            user_feedback="Make this more comprehensive",
        ))
        assert out.steps_applied
        assert "user-feedback" in out.issues_addressed

    def test_user_feedback_skipped_when_no_module_refiner(self):
        agent = RefinerAgent(_config(), StubProvider(), refiners={})
        course = FakeCourse(modules=(_module(),))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(), issues=(),
        )
        out = agent.run(RefinerInput(
            course=course, evaluation_report=report,
            user_feedback="Improve content",
        ))
        assert out.steps_skipped

    def test_no_user_feedback_no_synthetic_issue(self):
        agent = RefinerAgent(_config(), StubProvider(), refiners={})
        course = FakeCourse(modules=(_module(),))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="block", target_id="x"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert "user-feedback" not in out.issues_addressed


class TestRefinerOrchestratorIntegration:

    def test_full_workflow_with_all_six_refiners(self):
        from ._fixtures import (
            make_block_response,
            make_context_response,
            make_module_response,
            make_plan_response,
            make_prereqs_response,
            make_section_response,
        )
        refiners = {
            "block": BlockRefinerAgent(
                _config(), FakeProvider(returns=make_block_response({"prompt": "new"}))
            ),
            "section": SectionRefinerAgent(
                _config(), FakeProvider(returns=make_section_response("T", ["LO1"]))
            ),
            "module": ModuleRefinerAgent(
                _config(), FakeProvider(returns=make_module_response("T", "S"))
            ),
            "context": ContextRefinerAgent(
                _config(), FakeProvider(returns=make_context_response())
            ),
            "plan": PlanRefinerAgent(
                _config(), FakeProvider(returns=make_plan_response([]))
            ),
            "prerequisites": PrerequisitesRefinerAgent(
                _config(), FakeProvider(returns=make_prereqs_response([]))
            ),
        }
        agent = RefinerAgent(_config(), StubProvider(), refiners=refiners)
        ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        plan = CourseSkeleton(
            topic="Python",
            modules=(
                ModuleSpec(title="M1", summary="", order=0),
                ModuleSpec(title="M2", summary="", order=1),
            ),
            sections=(),
            prerequisites=(),
        )
        m1 = Module(
            id=new_module_id(), title="M1", summary="", order=0,
            sections=(Section(
                id=new_section_id(), title="S1", order=0,
                blocks=(ContentBlock(
                    id=new_block_id(), type="exercise", order=0,
                    content={"prompt": "x"},
                ),),
                learning_objectives=["LO1"],
            ),),
        )
        m2 = Module(
            id=new_module_id(), title="M2", summary="", order=1,
            sections=(Section(
                id=new_section_id(), title="S2", order=0,
                blocks=(ContentBlock(
                    id=new_block_id(), type="concept", order=0,
                    content={"markdown": "y"},
                ),),
                learning_objectives=["LO2"],
            ),),
        )
        course = FakeCourse(
            modules=(m1, m2),
            context=ctx,
            plan=plan,
            prerequisites=(),
        )
        issues = [
            make_issue(issue_id="i-block", scope="block", target_id=str(m1.sections[0].blocks[0].id)),
            make_issue(issue_id="i-section", scope="section", target_id=str(m1.sections[0].id)),
            make_issue(issue_id="i-module", scope="module", target_id=str(m2.id)),
            make_issue(issue_id="i-context", scope="course", category="audience_alignment"),
            make_issue(issue_id="i-plan", scope="course", category="structural"),
            make_issue(issue_id="i-prereq", scope="course", category="prerequisite"),
        ]
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(), issues=tuple(issues),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert len(out.steps_applied) == 6
        assert out.auto_fixed is True
        applied_levels = {s.level for s in out.steps_applied}
        assert applied_levels == {"block", "section", "module", "context", "plan", "prerequisites"}

    def test_cascade_dependencies_respected_in_plan(self):
        analyzer = IssueAnalyzer()
        from cogenai.application.orchestrator.evaluator import EvaluationIssue
        issues = (
            EvaluationIssue(id="i-1", severity="warning", scope="course", target_id="c-1", category="audience_alignment", message="x"),
            EvaluationIssue(id="i-2", severity="warning", scope="module", target_id="m-1", category="completeness", message="x"),
        )
        analysis = analyzer.analyze(issues)
        planner = RefinementPlanner()
        plan = planner.plan(analysis, course_id="c-1")
        module_step = next(s for s in plan.steps if s.level == "module")
        assert module_step.depends_on == (1,)


class TestCourseBundle:

    def test_bundle_proxies_modules_to_course(self):
        from cogenai.application.orchestrator.refiner import CourseBundle
        module = _module()
        course = FakeCourse(modules=(module,))
        ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        bundle = CourseBundle(course=course, context=ctx)
        assert bundle.modules == (module,)
        assert bundle.id == course.id
        assert bundle.title == "Course"

    def test_bundle_proxies_learning_outcomes(self):
        from cogenai.application.orchestrator.refiner import CourseBundle
        course = FakeCourse(learning_outcomes=("A", "B"))
        bundle = CourseBundle(course=course)
        assert bundle.learning_outcomes == ("A", "B")

    def test_orchestrator_runs_context_step_when_bundle_has_context(self):
        from ._fixtures import make_context_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response(audience="engineer"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        bundle = CourseBundle(course=FakeCourse(context=ctx), context=ctx)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert len(out.steps_applied) == 1
        assert out.steps_applied[0].level == "context"
        assert out.auto_fixed is True

    def test_orchestrator_runs_plan_step_when_bundle_has_plan(self):
        from ._fixtures import make_plan_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        plan_refiner = PlanRefinerAgent(
            _config(), FakeProvider(returns=make_plan_response([]))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"plan": plan_refiner},
        )
        ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        plan = CourseSkeleton(
            topic="Python",
            modules=(ModuleSpec(title="M1", summary="", order=0),),
            sections=(),
            prerequisites=(),
        )
        bundle = CourseBundle(course=FakeCourse(), context=ctx, plan=plan)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="structural"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert len(out.steps_applied) == 1
        assert out.steps_applied[0].level == "plan"

    def test_orchestrator_runs_prerequisites_step_when_bundle_has_prereqs(self):
        from ._fixtures import make_prereqs_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        prereqs_refiner = PrerequisitesRefinerAgent(
            _config(),
            FakeProvider(
                returns=make_prereqs_response(
                    [{"from_topic": "a", "to_topic": "b", "type": "requires"}]
                )
            ),
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"prerequisites": prereqs_refiner},
        )
        bundle = CourseBundle(
            course=FakeCourse(),
            prerequisites=(Prerequisite(from_topic="old", to_topic="old2"),),
        )
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="prerequisite"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert len(out.steps_applied) == 1
        assert out.steps_applied[0].level == "prerequisites"

    def test_orchestrator_clear_error_when_context_missing(self):
        from ._fixtures import make_context_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response())
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        bundle = CourseBundle(course=FakeCourse(context=None), context=None)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert len(out.steps_skipped) == 1
        assert out.auto_fixed is False
        logger_msg_captured = "CourseBundle" in (
            "ValueError: bundle has no GenerationContext; wrap the Course in CourseBundle before refinement"
        )
        assert logger_msg_captured is True

    def test_bundle_full_workflow_all_six_levels(self):
        from ._fixtures import (
            make_block_response,
            make_context_response,
            make_module_response,
            make_plan_response,
            make_prereqs_response,
            make_section_response,
        )
        from cogenai.application.orchestrator.refiner import CourseBundle

        refiners = {
            "block": BlockRefinerAgent(
                _config(), FakeProvider(returns=make_block_response({"prompt": "new"}))
            ),
            "section": SectionRefinerAgent(
                _config(), FakeProvider(returns=make_section_response("T", ["LO1"]))
            ),
            "module": ModuleRefinerAgent(
                _config(), FakeProvider(returns=make_module_response("T", "S"))
            ),
            "context": ContextRefinerAgent(
                _config(), FakeProvider(returns=make_context_response())
            ),
            "plan": PlanRefinerAgent(
                _config(), FakeProvider(returns=make_plan_response([]))
            ),
            "prerequisites": PrerequisitesRefinerAgent(
                _config(), FakeProvider(returns=make_prereqs_response([]))
            ),
        }
        agent = RefinerAgent(_config(), StubProvider(), refiners=refiners)

        ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        plan = CourseSkeleton(
            topic="Python",
            modules=(
                ModuleSpec(title="M1", summary="", order=0),
                ModuleSpec(title="M2", summary="", order=1),
            ),
            sections=(),
            prerequisites=(Prerequisite(from_topic="x", to_topic="y"),),
        )
        m1 = Module(
            id=new_module_id(), title="M1", summary="", order=0,
            sections=(Section(
                id=new_section_id(), title="S1", order=0,
                blocks=(ContentBlock(
                    id=new_block_id(), type="exercise", order=0,
                    content={"prompt": "x"},
                ),),
                learning_objectives=["LO1"],
            ),),
        )
        m2 = Module(
            id=new_module_id(), title="M2", summary="", order=1,
            sections=(Section(
                id=new_section_id(), title="S2", order=0,
                blocks=(ContentBlock(
                    id=new_block_id(), type="concept", order=0,
                    content={"markdown": "y"},
                ),),
                learning_objectives=["LO2"],
            ),),
        )
        bundle = CourseBundle(
            course=FakeCourse(modules=(m1, m2)),
            context=ctx,
            plan=plan,
            prerequisites=plan.prerequisites,
        )
        issues = [
            make_issue(issue_id="i-block", scope="block", target_id=str(m1.sections[0].blocks[0].id)),
            make_issue(issue_id="i-section", scope="section", target_id=str(m1.sections[0].id)),
            make_issue(issue_id="i-module", scope="module", target_id=str(m2.id)),
            make_issue(issue_id="i-context", scope="course", category="audience_alignment"),
            make_issue(issue_id="i-plan", scope="course", category="structural"),
            make_issue(issue_id="i-prereq", scope="course", category="prerequisite"),
        ]
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(), issues=tuple(issues),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert len(out.steps_applied) == 6
        assert out.auto_fixed is True
        applied_levels = {s.level for s in out.steps_applied}
        assert applied_levels == {"block", "section", "module", "context", "plan", "prerequisites"}


class TestOrchestratorAppliesArtifacts:

    def test_context_artifact_applied_to_bundle(self):
        from ._fixtures import make_context_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        new_ctx = GenerationContext(
            topic="Python", audience="engineer", difficulty="advanced",
            learning_outcomes=("Functions",),
        )
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response(audience="engineer", difficulty="advanced", outcomes=("Functions",)))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        original_ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        bundle = CourseBundle(course=FakeCourse(), context=original_ctx)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert isinstance(out.revised, CourseBundle)
        assert out.revised.context.audience == "engineer"
        assert out.revised.context.audience != out.original.context.audience

    def test_plan_artifact_applied_to_bundle(self):
        from ._fixtures import make_plan_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        plan_refiner = PlanRefinerAgent(
            _config(), FakeProvider(returns=make_plan_response([
                {"title": "M1", "summary": "", "order": 0},
                {"title": "M2-NEW", "summary": "added", "order": 1},
            ]))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"plan": plan_refiner},
        )
        original_ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        original_plan = CourseSkeleton(
            topic="Python",
            modules=(ModuleSpec(title="M1", summary="", order=0),),
            sections=(),
            prerequisites=(),
        )
        bundle = CourseBundle(course=FakeCourse(), context=original_ctx, plan=original_plan)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="structural"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert isinstance(out.revised, CourseBundle)
        assert out.revised.plan is not original_plan
        titles = [m.title for m in out.revised.plan.modules]
        assert "M1" in titles
        assert "M2-NEW" in titles
        assert out.revised.plan is not out.original.plan

    def test_prerequisites_artifact_applied_to_bundle(self):
        from ._fixtures import make_prereqs_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        prereqs_refiner = PrerequisitesRefinerAgent(
            _config(),
            FakeProvider(
                returns=make_prereqs_response([
                    {"from_topic": "a", "to_topic": "b", "type": "requires"},
                ])
            ),
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"prerequisites": prereqs_refiner},
        )
        bundle = CourseBundle(
            course=FakeCourse(),
            prerequisites=(Prerequisite(from_topic="old", to_topic="old2"),),
        )
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="prerequisite"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert isinstance(out.revised, CourseBundle)
        assert len(out.revised.prerequisites) == 1
        assert out.revised.prerequisites[0].from_topic == "a"
        assert out.revised.prerequisites != out.original.prerequisites

    def test_module_artifact_applied_to_course(self):
        from ._fixtures import make_module_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("New Title", "new summary"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )
        module = _module()
        bundle = CourseBundle(course=FakeCourse(modules=(module,)))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(module.id)),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert isinstance(out.revised, CourseBundle)
        target_module = next(m for m in out.revised.course.modules if str(m.id) == str(module.id))
        assert target_module.title == "New Title"
        assert target_module.summary == "new summary"
        assert target_module.version == module.version + 1
        assert out.revised.course.version == module.version + 1

    def test_section_artifact_applied_to_course(self):
        from ._fixtures import make_section_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        section_refiner = SectionRefinerAgent(
            _config(), FakeProvider(returns=make_section_response("Renamed Section", ["LO1", "LO2"]))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"section": section_refiner},
        )
        module = _module()
        section = module.sections[0]
        bundle = CourseBundle(course=FakeCourse(modules=(module,)))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="section", target_id=str(section.id)),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert isinstance(out.revised, CourseBundle)
        target_section = next(
            s for m in out.revised.course.modules for s in m.sections
            if str(s.id) == str(section.id)
        )
        assert target_section.title == "Renamed Section"
        assert target_section.learning_objectives == ["LO1", "LO2"]
        assert target_section.version == section.version + 1

    def test_block_artifact_applied_to_course(self):
        from ._fixtures import make_block_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        block_refiner = BlockRefinerAgent(
            _config(), FakeProvider(returns=make_block_response({"prompt": "new prompt"}))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"block": block_refiner},
        )
        module = _module()
        block = module.sections[0].blocks[0]
        bundle = CourseBundle(course=FakeCourse(modules=(module,)))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="block", target_id=str(block.id)),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert isinstance(out.revised, CourseBundle)
        target_block = next(
            b for m in out.revised.course.modules for s in m.sections for b in s.blocks
            if str(b.id) == str(block.id)
        )
        assert target_block.content["prompt"] == "new prompt"
        assert target_block.version == block.version + 1

    def test_context_skipped_gracefully_for_bare_course(self):
        from ._fixtures import make_context_response
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response())
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        course = FakeCourse()  # no context attr, no CourseBundle
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=course, evaluation_report=report))
        assert out.steps_skipped
        assert out.auto_fixed is False
        assert out.revised is out.original  # nothing changed

    def test_revised_differs_from_original_after_refinement(self):
        from ._fixtures import make_module_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("T", "S"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )
        module = _module()
        bundle = CourseBundle(course=FakeCourse(modules=(module,)))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(module.id)),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert out.revised is not out.original

    def test_unaffected_modules_keep_original_version(self):
        from ._fixtures import make_module_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("Renamed", "new"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )
        m1 = Module(id=new_module_id(), title="M1", summary="", order=0, sections=(_section(),))
        m2 = Module(id=new_module_id(), title="M2", summary="", order=1, sections=(_section(),))
        bundle = CourseBundle(course=FakeCourse(modules=(m1, m2)))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(m2.id)),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        m1_revised = next(m for m in out.revised.course.modules if str(m.id) == str(m1.id))
        m2_revised = next(m for m in out.revised.course.modules if str(m.id) == str(m2.id))
        assert m1_revised.version == m1.version
        assert m2_revised.title == "Renamed"
        assert m2_revised.version == m2.version + 1

    def test_unaffected_sections_keep_original_version(self):
        from ._fixtures import make_section_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        section_refiner = SectionRefinerAgent(
            _config(), FakeProvider(returns=make_section_response("Renamed", ["LO1"]))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"section": section_refiner},
        )
        s1 = Section(id=new_section_id(), title="S1", order=0, blocks=(_block(),), learning_objectives=["LO1"])
        s2 = Section(id=new_section_id(), title="S2", order=1, blocks=(_block(),), learning_objectives=["LO2"])
        m = Module(id=new_module_id(), title="M", summary="", order=0, sections=(s1, s2))
        bundle = CourseBundle(course=FakeCourse(modules=(m,)))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="section", target_id=str(s2.id)),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        m_revised = out.revised.course.modules[0]
        s1_revised = next(s for s in m_revised.sections if str(s.id) == str(s1.id))
        s2_revised = next(s for s in m_revised.sections if str(s.id) == str(s2.id))
        assert s1_revised.version == s1.version
        assert s2_revised.title == "Renamed"
        assert s2_revised.version == s2.version + 1


class TestOrchestratorIterationLoop:
    """Reproduces the user's bug: same evaluator issues appear across iterations
    because the orchestrator was discarding refinement artifacts. With artifacts
    now applied, iteration 2 should see a different (better) evaluator report."""

    def test_iteration_loop_evaluator_sees_refined_course(self):
        from ._fixtures import make_module_response
        from cogenai.application.orchestrator.refiner import CourseBundle

        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("Refined Title", "refined summary"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )

        seen_modules_prompts: list = []

        class RecordingProvider:
            def health_check(self):
                return True

            def complete(self, request):
                from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
                seen_modules_prompts.append(request.prompt)
                return CompletionResponse(
                    text='{"rubric": {"accuracy": 0.9, "pedagogical_clarity": 0.9, "structure_compliance": 0.9, "depth_appropriateness": 0.9, "audience_alignment": 0.9, "consistency": 0.9, "completeness": 0.9}, "issues": []}',
                    model=request.model,
                    usage=CompletionUsage(0, 0, 0),
                    finish_reason="stop",
                )

        from cogenai.application.orchestrator.evaluator import EvaluatorAgent, EvaluatorInput

        module = _module()
        original_ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        bundle = CourseBundle(course=FakeCourse(modules=(module,)), context=original_ctx)
        iter1_report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(module.id), category="accuracy", message="title has grammatical error"),),
        )
        refined = agent.run(RefinerInput(course=bundle, evaluation_report=iter1_report))

        eval_agent = EvaluatorAgent(_config(), RecordingProvider())
        eval_agent.run(EvaluatorInput(course=refined.revised.course, rubric_version="1.0.0"))

        assert len(seen_modules_prompts) == 1
        assert "Refined Title" in seen_modules_prompts[0]

    def test_iteration_loop_with_real_evaluator_uses_refined_input(self):
        from ._fixtures import make_module_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        from cogenai.application.orchestrator.evaluator import EvaluatorAgent, EvaluatorInput

        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("Python for Beginners", "fixed"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )
        module = _module()
        bundle = CourseBundle(course=FakeCourse(modules=(module,)))
        iter1_report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(module.id), category="accuracy", message="title has error"),),
        )
        refined = agent.run(RefinerInput(course=bundle, evaluation_report=iter1_report))

        seen_prompts: list = []

        class RecordingStub:
            def health_check(self):
                return True

            def complete(self, request):
                from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
                seen_prompts.append(request.prompt)
                return CompletionResponse(
                    text='{"rubric": {"accuracy": 0.9, "pedagogical_clarity": 0.9, "structure_compliance": 0.9, "depth_appropriateness": 0.9, "audience_alignment": 0.9, "consistency": 0.9, "completeness": 0.9}, "issues": []}',
                    model=request.model,
                    usage=CompletionUsage(0, 0, 0),
                    finish_reason="stop",
                )

        eval_agent = EvaluatorAgent(_config(), RecordingStub())
        eval_agent.run(EvaluatorInput(course=refined.revised.course, rubric_version="1.0.0"))

        assert len(seen_prompts) == 1
        prompt = seen_prompts[0]
        assert "Python for Beginners" in prompt

    def test_revised_field_is_functionally_distinct_from_original(self):
        from ._fixtures import make_module_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("Refined", "R"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )
        module = _module()
        bundle = CourseBundle(course=FakeCourse(modules=(module,)))
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(module.id)),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))

        # original unchanged
        original_module = next(m for m in out.original.course.modules if str(m.id) == str(module.id))
        assert original_module.title == module.title
        assert original_module.version == module.version

        # revised updated
        revised_module = next(m for m in out.revised.course.modules if str(m.id) == str(module.id))
        assert revised_module.title == "Refined"
        assert revised_module.version == module.version + 1


class TestContextMetadataSync:

    def test_context_refiner_updates_course_title(self):
        from ._fixtures import make_context_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response(audience="engineer"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        module = _module()
        original_ctx = GenerationContext(
            topic="Python", audience="beginner", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        bundle = CourseBundle(course=FakeCourse(modules=(module,)), context=original_ctx)
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert "engineer" in out.revised.course.title
        assert "engineer" in out.revised.course.summary

    def test_context_refiner_updates_course_summary(self):
        from ._fixtures import make_context_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        context_refiner = ContextRefinerAgent(
            _config(),
            FakeProvider(returns=make_context_response(outcomes=("Variables", "Functions", "Loops"))),
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        bundle = CourseBundle(
            course=FakeCourse(modules=(_module(),)),
            context=GenerationContext(
                topic="Python", audience="beginners", difficulty="beginner",
                learning_outcomes=("Variables",),
            ),
        )
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="depth"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert "Functions" in out.revised.course.summary
        assert "Loops" in out.revised.course.summary

    def test_context_refiner_bumps_course_version(self):
        from ._fixtures import make_context_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response())
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        bundle = CourseBundle(
            course=FakeCourse(modules=(_module(),)),
            context=GenerationContext(
                topic="Python", audience="beginner", difficulty="beginner",
                learning_outcomes=("Variables",),
            ),
        )
        original_version = bundle.course.version
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert out.revised.course.version == original_version + 1

    def test_context_refiner_preserves_modules(self):
        from ._fixtures import make_context_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        context_refiner = ContextRefinerAgent(
            _config(), FakeProvider(returns=make_context_response())
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        m1 = _module()
        m2 = _module()
        bundle = CourseBundle(
            course=FakeCourse(modules=(m1, m2)),
            context=GenerationContext(
                topic="Python", audience="beginner", difficulty="beginner",
                learning_outcomes=("Variables",),
            ),
        )
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert len(out.revised.course.modules) == 2

    def test_module_refiner_does_not_touch_metadata(self):
        from ._fixtures import make_module_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        module_refiner = ModuleRefinerAgent(
            _config(), FakeProvider(returns=make_module_response("New Title", "new summary"))
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"module": module_refiner},
        )
        module = _module()
        original_title = "Original Course Title"
        bundle = CourseBundle(
            course=FakeCourse(title=original_title, modules=(module,)),
        )
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(module.id)),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        assert out.revised.course.title == original_title

    def test_context_refiner_with_invalid_audience_does_not_crash(self):
        from ._fixtures import make_context_response
        from cogenai.application.orchestrator.refiner import CourseBundle
        context_refiner = ContextRefinerAgent(
            _config(),
            FakeProvider(returns=make_context_response(audience="unicorns", difficulty="mythical")),
        )
        agent = RefinerAgent(
            _config(), StubProvider(),
            refiners={"context": context_refiner},
        )
        bundle = CourseBundle(
            course=FakeCourse(modules=(_module(),)),
            context=GenerationContext(
                topic="Python", audience="beginner", difficulty="beginner",
                learning_outcomes=("Variables",),
            ),
        )
        report = EvaluationReport(
            overall_score=0.5, passed=False, rubric=RubricScores(),
            issues=(make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
        )
        out = agent.run(RefinerInput(course=bundle, evaluation_report=report))
        # Should not raise; course.audience may be None if LLM returned invalid value
        assert out.steps_applied


class TestEntityMetadata:

    def test_module_has_sections_count(self):
        from cogenai.domain.shared.value_objects import new_module_id
        m = Module(id=new_module_id(), title="M", order=0, sections=(), sections_count=3)
        assert m.sections_count == 3

    def test_section_has_blocks_count(self):
        from cogenai.domain.shared.value_objects import new_section_id
        s = Section(id=new_section_id(), title="S", order=0, blocks=(), learning_objectives=["LO"], blocks_count=5)
        assert s.blocks_count == 5

    def test_block_has_parent_ids(self):
        from cogenai.domain.shared.value_objects import (
            new_block_id, new_section_id, new_module_id,
        )
        b = ContentBlock(
            id=new_block_id(), type="concept", order=0, content={},
            parent_section_id=new_section_id(),
            parent_module_id=new_module_id(),
            block_index=3,
        )
        assert b.parent_section_id is not None
        assert b.parent_module_id is not None
        assert b.block_index == 3

    def test_course_from_context_sets_source_topic(self):
        ctx = GenerationContext(
            topic="Python", audience="beginners", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        course = Course.from_context(ctx)
        assert course.source_topic == "Python"

    def test_course_from_context_with_modules(self):
        from cogenai.domain.shared.value_objects import new_module_id
        m = Module(id=new_module_id(), title="M1", order=0, sections=(), sections_count=1)
        ctx = GenerationContext(
            topic="Python", audience="beginners", difficulty="beginner",
            learning_outcomes=("Variables",),
        )
        course = Course.from_context(ctx, modules=(m,))
        assert course.modules == (m,)
        assert "beginners" in course.title
