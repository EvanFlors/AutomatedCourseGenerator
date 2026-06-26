from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from cogenai.application.agents.base import BaseAgent
from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.context_synthesizer import GenerationContext
from cogenai.application.orchestrator.curriculum_planner import (
    CourseSkeleton,
    Prerequisite,
)
from cogenai.application.orchestrator.evaluator import EvaluationIssue, EvaluationReport
from cogenai.application.orchestrator.refiners import (
    BlockRefinerInput,
    ContextRefinerInput,
    IssueAnalyzer,
    MetadataRefinerInput,
    ModuleRefinerInput,
    PlanRefinerInput,
    PrerequisitesRefinerInput,
    RefinementPlanner,
    RefinementStep,
    RefinerError,
    SectionRefinerInput,
)
from cogenai.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CourseBundle:
    """Wrapper that gives the orchestrator access to all data the granular refiners need.

    The bare Course entity carries modules/sections/blocks (for module/section/block
    refinement) but not the context, plan, or prerequisites (which live in the
    generation pipeline). This bundle exposes everything via attribute access:

        bundle.course        -> Course entity
        bundle.context       -> GenerationContext (for context_refiner)
        bundle.plan          -> CourseSkeleton   (for plan_refiner)
        bundle.prerequisites -> tuple[Prerequisite, ...] (for prerequisites_refiner)
        bundle.modules       -> proxies to bundle.course.modules

    Pass this as `input_data.course` to RefinerInput.
    """

    course: Any
    context: GenerationContext | None = None
    plan: CourseSkeleton | None = None
    prerequisites: tuple[Prerequisite, ...] = field(default_factory=tuple)

    @property
    def modules(self) -> tuple:
        return tuple(getattr(self.course, "modules", ()))

    @property
    def id(self) -> Any:
        return getattr(self.course, "id", None)

    @property
    def title(self) -> str:
        return str(getattr(self.course, "title", ""))

    @property
    def learning_outcomes(self) -> tuple[str, ...]:
        return tuple(getattr(self.course, "learning_outcomes", ()))


@dataclass
class RefinerInput:
    course: Any
    evaluation_report: EvaluationReport
    user_feedback: str = ""


@dataclass
class RefinementStepResult:
    step: RefinementStep
    success: bool
    artifact: Any = None
    error: str | None = None
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class RefinedDraft:
    original: Any
    revised: Any
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)
    auto_fixed: bool = False
    refinement_notes: str = ""
    steps_applied: tuple[RefinementStep, ...] = field(default_factory=tuple)
    steps_skipped: tuple[RefinementStep, ...] = field(default_factory=tuple)


class BudgetExceeded(Exception):

    def __init__(self, used: int, cap: int, level: str = ""):
        self.used = used
        self.cap = cap
        self.level = level
        super().__init__(f"token budget exhausted ({used}/{cap}) at level={level!r}")


def sum_tokens(artifact: Any) -> int:
    """Sum input + output tokens from a refiner artifact (best-effort)."""
    tokens = getattr(artifact, "tokens_used", None)
    if tokens is None:
        return 0
    in_t = int(getattr(tokens, "input_tokens", 0) or 0)
    out_t = int(getattr(tokens, "output_tokens", 0) or 0)
    total = int(getattr(tokens, "total_tokens", in_t + out_t) or 0)
    return total if total else (in_t + out_t)


class RefinerAgent(BaseAgent[RefinerInput, RefinedDraft]):

    def __init__(
        self,
        config: AgentConfig,
        llm_provider,
        refiners: dict[str, BaseAgent] | None = None,
    ):
        super().__init__(name="refiner", config=config, llm_provider=llm_provider)
        self.refiners: dict[str, BaseAgent] = dict(refiners or {})
        self._analyzer = IssueAnalyzer()
        self._planner = RefinementPlanner()

    def run(self, input_data: RefinerInput, *, token_budget: int | None = None) -> RefinedDraft:
        issues = self._collect_issues(input_data)
        analysis = self._analyzer.analyze(issues)
        course_id = str(getattr(input_data.course, "id", "course"))
        plan = self._planner.plan(analysis, course_id=course_id)

        applied_steps: list[RefinementStep] = []
        skipped_steps: list[RefinementStep] = []
        all_addressed: list[str] = []
        course: Any = input_data.course
        tokens_used = 0
        budget_exhausted = False
        budget_exhausted_level = ""

        for step in plan.steps:
            if budget_exhausted:
                skipped_steps.append(step)
                continue
            try:
                result = self._execute_step(step, input_data, issues)
            except BudgetExceeded as exc:
                budget_exhausted = True
                budget_exhausted_level = exc.level
                skipped_steps.append(step)
                break
            if not result.success:
                skipped_steps.append(result.step)
                continue
            tokens_used += self._sum_tokens(result.artifact)

            if token_budget is not None and tokens_used > token_budget:
                budget_exhausted = True
                budget_exhausted_level = step.level
                skipped_steps.append(step)
                logger.warning(
                    "refinement_budget_exhausted",
                    used=tokens_used, cap=token_budget, level=step.level,
                )
                break
            course = self._apply_artifact(course, step.level, result.artifact)
            applied_steps.append(result.step)
            all_addressed.extend(result.issues_addressed)

        notes = plan.rationale
        if budget_exhausted:
            notes = f"{notes}; budget_exhausted at level={budget_exhausted_level} ({tokens_used}/{token_budget} tokens)"

        refined = RefinedDraft(
            original=input_data.course,
            revised=course,
            issues_addressed=tuple(all_addressed),
            auto_fixed=bool(applied_steps),
            refinement_notes=notes,
            steps_applied=tuple(applied_steps),
            steps_skipped=tuple(skipped_steps),
        )
        self._log_execution(input_data, refined)
        return refined

    @staticmethod
    def _sum_tokens(artifact: Any) -> int:
        return sum_tokens(artifact)

    def _collect_issues(self, input_data: RefinerInput) -> tuple[EvaluationIssue, ...]:
        issues: list[EvaluationIssue] = list(input_data.evaluation_report.issues)
        if input_data.user_feedback:
            issues.append(self._make_feedback_issue(input_data))
        return tuple(issues)

    def _make_feedback_issue(self, input_data: RefinerInput) -> EvaluationIssue:
        return EvaluationIssue(
            id="user-feedback",
            severity="warning",
            scope="module",
            target_id=self._feedback_target_id(input_data),
            category="user_feedback",
            message=input_data.user_feedback,
            suggestion=input_data.user_feedback,
            auto_fixable=False,
        )

    def _feedback_target_id(self, input_data: RefinerInput) -> str:
        course = input_data.course
        for m in getattr(course, "modules", ()):
            mid = getattr(m, "id", None)
            if mid is not None:
                return str(mid)
        return str(getattr(course, "id", ""))

    def _execute_step(
        self,
        step: RefinementStep,
        input_data: RefinerInput,
        issues: tuple[EvaluationIssue, ...],
    ) -> RefinementStepResult:
        refiner = self.refiners.get(step.level)
        if refiner is None:
            return RefinementStepResult(
                step=step,
                success=False,
                error=f"No refiner registered for level={step.level}",
            )
        step_issues = tuple(i for i in issues if i.id in step.issue_ids)
        try:
            artifact = self._dispatch(refiner, step, input_data, step_issues)
            return RefinementStepResult(
                step=step,
                success=True,
                artifact=artifact,
                issues_addressed=tuple(i.id for i in step_issues),
            )
        except RefinerError as exc:
            return RefinementStepResult(step=step, success=False, error=str(exc))
        except (KeyError, ValueError, AttributeError) as exc:
            return RefinementStepResult(step=step, success=False, error=f"{type(exc).__name__}: {exc}")

    def _dispatch(
        self,
        refiner: BaseAgent,
        step: RefinementStep,
        input_data: RefinerInput,
        step_issues: tuple[EvaluationIssue, ...],
    ) -> Any:
        if step.level == "context":
            return self._run_context(refiner, input_data, step_issues)
        if step.level == "metadata":
            return self._run_metadata(refiner, input_data, step_issues)
        if step.level == "prerequisites":
            return self._run_prerequisites(refiner, input_data, step_issues)
        if step.level == "plan":
            return self._run_plan(refiner, input_data, step_issues)
        if step.level == "module":
            return self._run_module(refiner, step, input_data, step_issues)
        if step.level == "section":
            return self._run_section(refiner, step, input_data, step_issues)
        if step.level == "block":
            return self._run_block(refiner, step, input_data, step_issues)
        raise ValueError(f"Unknown refiner level: {step.level}")

    def _run_context(
        self,
        refiner: BaseAgent,
        input_data: RefinerInput,
        step_issues: tuple[EvaluationIssue, ...],
    ) -> Any:
        course = input_data.course
        ctx = getattr(course, "context", None)
        if not isinstance(ctx, GenerationContext):
            raise ValueError(
                "bundle has no GenerationContext; wrap the Course in CourseBundle before refinement"
            )
        inp = ContextRefinerInput(
            course_id=getattr(course, "id", "course"),
            current_context=ctx,
            issues=step_issues,
            user_feedback=input_data.user_feedback,
        )
        return refiner.run(inp)

    def _run_metadata(
        self,
        refiner: BaseAgent,
        input_data: RefinerInput,
        step_issues: tuple[EvaluationIssue, ...],
    ) -> Any:
        from cogenai.application.orchestrator.refiners.metadata_refiner import (
            _compute_duration_minutes,
        )
        course = input_data.course
        ctx = getattr(course, "context", None)
        inp = MetadataRefinerInput(
            course_id=getattr(course, "id", "course"),
            current_tags=tuple(getattr(course, "tags", ())),
            current_language=str(getattr(course, "language", "en")),
            current_duration_minutes=_compute_duration_minutes(course),
            topic=str(getattr(ctx, "topic", "")) if ctx is not None else "",
            audience=str(getattr(ctx, "audience", "")) if ctx is not None else "",
            difficulty=str(getattr(ctx, "difficulty", "")) if ctx is not None else "",
            issues=step_issues,
        )
        return refiner.run(inp)

    def _run_prerequisites(
        self,
        refiner: BaseAgent,
        input_data: RefinerInput,
        step_issues: tuple[EvaluationIssue, ...],
    ) -> Any:
        course = input_data.course
        current = getattr(course, "prerequisites", ())
        if current and not isinstance(current[0], Prerequisite):
            raise ValueError(
                "bundle.prerequisites must be a tuple of Prerequisite; "
                "wrap the Course in CourseBundle to provide them"
            )
        inp = PrerequisitesRefinerInput(
            course_id=getattr(course, "id", "course"),
            current_prerequisites=tuple(current),
            issues=step_issues,
            course_topic=str(getattr(course, "title", "")),
        )
        return refiner.run(inp)

    def _run_plan(
        self,
        refiner: BaseAgent,
        input_data: RefinerInput,
        step_issues: tuple[EvaluationIssue, ...],
    ) -> Any:
        course = input_data.course
        plan = getattr(course, "plan", None)
        if not isinstance(plan, CourseSkeleton):
            raise ValueError(
                "bundle has no CourseSkeleton; wrap the Course in CourseBundle before refinement"
            )
        ctx = getattr(course, "context", None) or GenerationContext(
            topic=str(getattr(course, "title", "")),
            audience="beginner",
            difficulty="beginner",
            learning_outcomes=tuple(getattr(course, "learning_outcomes", ())),
        )
        inp = PlanRefinerInput(
            course_id=getattr(course, "id", "course"),
            current_plan=plan,
            issues=step_issues,
            context=ctx,
            constraints=(),
        )
        return refiner.run(inp)

    def _run_module(
        self,
        refiner: BaseAgent,
        step: RefinementStep,
        input_data: RefinerInput,
        step_issues: tuple[EvaluationIssue, ...],
    ) -> Any:
        course = input_data.course
        module = self._find_module(course, step.target_id)
        if module is None:
            raise ValueError(f"module {step.target_id} not found")
        course_outline = tuple(m.title for m in getattr(course, "modules", ()))
        inp = ModuleRefinerInput(
            course_id=getattr(course, "id", step.target_id),
            current_module=module,
            course_outline=course_outline,
            issues=step_issues,
            context=getattr(course, "context", None),
        )
        return refiner.run(inp)

    def _run_section(
        self,
        refiner: BaseAgent,
        step: RefinementStep,
        input_data: RefinerInput,
        step_issues: tuple[EvaluationIssue, ...],
    ) -> Any:
        course = input_data.course
        section, module = self._find_section(course, step.target_id)
        if section is None:
            raise ValueError(f"section {step.target_id} not found")
        module_outline = (
            tuple(s.title for s in getattr(module, "sections", ())) if module else ()
        )
        inp = SectionRefinerInput(
            course_id=getattr(course, "id", step.target_id),
            current_section=section,
            module_outline=module_outline,
            issues=step_issues,
            context=getattr(course, "context", None),
        )
        return refiner.run(inp)

    def _run_block(
        self,
        refiner: BaseAgent,
        step: RefinementStep,
        input_data: RefinerInput,
        step_issues: tuple[EvaluationIssue, ...],
    ) -> Any:
        course = input_data.course
        block, section = self._find_block(course, step.target_id)
        if block is None:
            raise ValueError(f"block {step.target_id} not found")
        section_outline = (
            tuple(b.type for b in getattr(section, "blocks", ())) if section else ()
        )
        inp = BlockRefinerInput(
            course_id=getattr(course, "id", step.target_id),
            current_block=block,
            section_outline=section_outline,
            issues=step_issues,
            context=getattr(course, "context", None),
        )
        return refiner.run(inp)

    def _find_module(self, course: Any, target_id: str) -> Any:
        for m in getattr(course, "modules", ()):
            if str(getattr(m, "id", "")) == target_id:
                return m
        return None

    def _find_section(self, course: Any, target_id: str) -> tuple[Any, Any]:
        for m in getattr(course, "modules", ()):
            for s in getattr(m, "sections", ()):
                if str(getattr(s, "id", "")) == target_id:
                    return s, m
        return None, None

    def _find_block(self, course: Any, target_id: str) -> tuple[Any, Any]:
        for m in getattr(course, "modules", ()):
            for s in getattr(m, "sections", ()):
                for b in getattr(s, "blocks", ()):
                    if str(getattr(b, "id", "")) == target_id:
                        return b, s
        return None, None

    def _apply_artifact(self, course: Any, level: str, artifact: Any) -> Any:
        if level == "context":
            return self._apply_context(course, artifact)
        if level == "metadata":
            return self._apply_metadata(course, artifact)
        if level == "prerequisites":
            return self._apply_prerequisites(course, artifact)
        if level == "plan":
            return self._apply_plan(course, artifact)
        if level == "module":
            return self._apply_module(course, artifact)
        if level == "section":
            return self._apply_section(course, artifact)
        if level == "block":
            return self._apply_block_to_course(course, artifact)
        return course

    def _apply_context(self, course: Any, artifact: Any) -> Any:
        context = getattr(artifact, "context", artifact)
        if isinstance(course, CourseBundle):
            new_bundle = replace(course, context=context)
            try:
                new_bundle = self._sync_metadata_from_context(new_bundle, context)
            except Exception as exc:
                logger.warning("context_metadata_sync_skipped", error=str(exc))
            return new_bundle
        logger.warning(
            "refinement_context_skipped_no_bundle",
            reason="input_data.course is a bare Course without a CourseBundle wrapper",
        )
        return course

    def _sync_metadata_from_context(self, bundle: "CourseBundle", context: Any) -> Any:
        """Re-derive Course.title/summary/audience/difficulty/learning_outcomes
        from the refined GenerationContext.
        """
        from cogenai.domain.course import Course
        existing = bundle.course
        new_course = Course.from_context(
            context,
            modules=tuple(getattr(existing, "modules", ())),
            estimated_duration_minutes=getattr(existing, "estimated_duration_minutes", 0),
            tags=tuple(getattr(existing, "tags", ())),
            language=getattr(existing, "language", "en"),
        )
        rebuilt = existing.with_modules(
            tuple(getattr(existing, "modules", ())),
            getattr(existing, "version", 0) + 1,
        )
        from cogenai.domain.shared.value_objects import CourseId
        rebuilt = Course(
            id=existing.id,
            title=new_course.title,
            summary=new_course.summary,
            language=new_course.language,
            audience=new_course.audience,
            difficulty=new_course.difficulty,
            learning_outcomes=new_course.learning_outcomes,
            modules=tuple(getattr(existing, "modules", ())),
            estimated_duration_minutes=new_course.estimated_duration_minutes,
            tags=new_course.tags,
            version=getattr(existing, "version", 0) + 1,
            generation_iteration=getattr(existing, "generation_iteration", 0) + 1,
            source_topic=new_course.source_topic,
        )
        return replace(bundle, course=rebuilt)

    def _apply_prerequisites(self, course: Any, artifact: Any) -> Any:
        prereqs = getattr(artifact, "prerequisites", artifact)
        if isinstance(course, CourseBundle):
            return replace(course, prerequisites=tuple(prereqs))
        logger.warning(
            "refinement_prerequisites_skipped_no_bundle",
            reason="input_data.course is a bare Course without a CourseBundle wrapper",
        )
        return course

    def _apply_metadata(self, course: Any, artifact: Any) -> Any:
        if not isinstance(course, CourseBundle):
            logger.warning(
                "refinement_metadata_skipped_no_bundle",
                reason="input_data.course is a bare Course without a CourseBundle wrapper",
            )
            return course
        from cogenai.application.orchestrator.refiners.metadata_refiner import (
            MetadataRefinerOutput,
        )
        if not isinstance(artifact, MetadataRefinerOutput):
            return course
        existing = course.course
        from cogenai.domain.course import Course
        new_course = Course(
            id=existing.id,
            title=existing.title,
            summary=existing.summary,
            language=artifact.language,
            audience=existing.audience,
            difficulty=existing.difficulty,
            learning_outcomes=existing.learning_outcomes,
            modules=existing.modules,
            estimated_duration_minutes=int(artifact.estimated_duration_minutes or 0),
            tags=artifact.tags,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
            version=getattr(existing, "version", 0) + 1,
            generation_iteration=getattr(existing, "generation_iteration", 0) + 1,
            source_topic=existing.source_topic,
        )
        return replace(course, course=new_course)

    def _apply_plan(self, course: Any, artifact: Any) -> Any:
        plan = getattr(artifact, "plan", artifact)
        if isinstance(course, CourseBundle):
            return replace(course, plan=plan)
        logger.warning(
            "refinement_plan_skipped_no_bundle",
            reason="input_data.course is a bare Course without a CourseBundle wrapper",
        )
        return course

    def _apply_module(self, course: Any, artifact: Any) -> Any:
        new_module = getattr(artifact, "module", artifact)
        course_entity = course.course if isinstance(course, CourseBundle) else course
        new_modules = tuple(
            new_module if str(m.id) == str(new_module.id) else m
            for m in course_entity.modules
        )
        rebuilt = course_entity.with_modules(new_modules, course_entity.version + 1)
        if isinstance(course, CourseBundle):
            return replace(course, course=rebuilt)
        return rebuilt

    def _apply_section(self, course: Any, artifact: Any) -> Any:
        new_section = getattr(artifact, "section", artifact)
        course_entity = course.course if isinstance(course, CourseBundle) else course
        new_modules: list[Any] = []
        for module in course_entity.modules:
            if any(str(s.id) == str(new_section.id) for s in module.sections):
                new_sections = tuple(
                    new_section if str(s.id) == str(new_section.id) else s
                    for s in module.sections
                )
                rebuilt_module = module.with_sections(new_sections, module.version + 1)
                new_modules.append(rebuilt_module)
            else:
                new_modules.append(module)
        rebuilt = course_entity.with_modules(tuple(new_modules), course_entity.version + 1)
        if isinstance(course, CourseBundle):
            return replace(course, course=rebuilt)
        return rebuilt

    def _apply_block_to_course(self, course: Any, artifact: Any) -> Any:
        new_block = getattr(artifact, "block", artifact)
        course_entity = course.course if isinstance(course, CourseBundle) else course
        new_modules: list[Any] = []
        for module in course_entity.modules:
            new_module_sections: list[Any] = []
            replaced_in_module = False
            for section in module.sections:
                if any(str(b.id) == str(new_block.id) for b in section.blocks):
                    new_blocks = tuple(
                        new_block if str(b.id) == str(new_block.id) else b
                        for b in section.blocks
                    )
                    rebuilt_section = section.with_blocks(list(new_blocks), section.version + 1)
                    new_module_sections.append(rebuilt_section)
                    replaced_in_module = True
                else:
                    new_module_sections.append(section)
            if replaced_in_module:
                rebuilt_module = module.with_sections(
                    tuple(new_module_sections), module.version + 1
                )
                new_modules.append(rebuilt_module)
            else:
                new_modules.append(module)
        rebuilt = course_entity.with_modules(tuple(new_modules), course_entity.version + 1)
        if isinstance(course, CourseBundle):
            return replace(course, course=rebuilt)
        return rebuilt
