from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cogenai.application.agents.config import AgentAssignmentPolicy, AgentConfig
from cogenai.application.orchestrator.consistency_checker import (
    ConsistencyCheckerAgent,
    ConsistencyCheckerInput,
)
from cogenai.application.orchestrator.content_block_generator import (
    ContentBlockGeneratorAgent,
    ContentBlockGeneratorInput,
)
from cogenai.application.orchestrator.context_synthesizer import (
    ContextSynthesizerAgent,
    ContextSynthesizerInput,
    GenerationContext,
)
from cogenai.application.orchestrator.curriculum_planner import (
    CurriculumPlannerAgent,
    CurriculumPlannerInput,
)
from cogenai.application.orchestrator.evaluator import EvaluatorAgent, EvaluatorInput
from cogenai.application.orchestrator.persona_adapter import (
    PersonaAdapterAgent,
    PersonaAdapterInput,
)
from cogenai.application.orchestrator.prerequisite_validator import (
    PrerequisiteValidatorAgent,
    PrerequisiteValidatorInput,
)
from cogenai.application.orchestrator.refiner import CourseBundle, RefinerAgent, RefinerInput
from cogenai.application.orchestrator.refiners import (
    BlockRefinerAgent,
    ContextRefinerAgent,
    MetadataRefinerAgent,
    ModuleRefinerAgent,
    PlanRefinerAgent,
    PrerequisitesRefinerAgent,
    SectionRefinerAgent,
)
from cogenai.application.orchestrator.section_author import (
    SectionAuthorAgent,
    SectionAuthorInput,
)
from cogenai.shared.settings import default_token_budget, get_settings
from cogenai.infrastructure.container import get_llm_provider
from cogenai.shared.logging import configure_logging, get_logger
from cogenai.domain.course.entities import ContentBlock, Course, Module, Section
from cogenai.domain.shared.value_objects import new_module_id, new_section_id
from cogenai.interfaces.dto import create_contract
from cogenai.interfaces.dto.evaluation import EvaluationDTO, RubricScoresDTO
from cogenai.interfaces.dto.generation import RefinementDTO
from cogenai.interfaces.dto.generation_request import GenerationRequestDTO
from cogenai.interfaces.dto.issue import IssueDTO

logger = get_logger(__name__)


# ----------------------------------------------- #
# Helpers                                          #
# ----------------------------------------------- #

@dataclass
class IterationResult:
    iteration: int
    course: Course
    evaluation_score: float
    evaluation_passed: bool
    consistency_passed: bool
    prerequisites_passed: bool
    issues: tuple = field(default_factory=tuple)
    user_feedback: str = ""


def build_agent_config(
    model_name: str | None = None,
    assignments: AgentAssignmentPolicy | None = None,
) -> AgentConfig:
    settings = get_settings()
    default = model_name or settings.model or "stub"
    policy = assignments or AgentAssignmentPolicy(default_model=default)
    return AgentConfig.default(model_name=default, assignments=policy)


def build_refiners(config: AgentConfig, llm_provider) -> dict[str, Any]:
    """Construct the 7 granular refiner agents for the orchestrator."""
    return {
        "context": ContextRefinerAgent(config, llm_provider),
        "metadata": MetadataRefinerAgent(config, llm_provider),
        "prerequisites": PrerequisitesRefinerAgent(config, llm_provider),
        "plan": PlanRefinerAgent(config, llm_provider),
        "module": ModuleRefinerAgent(config, llm_provider),
        "section": SectionRefinerAgent(config, llm_provider),
        "block": BlockRefinerAgent(config, llm_provider),
    }


# ----------------------------------------------- #
# Phase 1: Course Generation                      #
# ----------------------------------------------- #

def generate_skeleton(
    request: GenerationRequestDTO,
    config: AgentConfig,
    llm_provider,
    feedback: str = "",
    prev_issues: tuple = (),
) -> tuple:
    """Run context synthesizer + curriculum planner. Returns (context, skeleton)."""
    enhanced_instructions = request.text_instructions
    if feedback:
        enhanced_instructions += f"\n\nUser Feedback: {feedback}"
    if prev_issues:
        issues_text = "\n".join(f"- [{i.severity}] {i.message}" for i in prev_issues[:5])
        enhanced_instructions += (
            f"\n\nPrevious Issues:\n{issues_text}"
            "\n\nImprovements needed: add depth, more modules, more block types."
        )

    ctx_agent = ContextSynthesizerAgent(config, llm_provider)
    context = ctx_agent.run(
        ContextSynthesizerInput(
            topic=request.topic,
            audience=request.audience,
            difficulty=request.difficulty,
            learning_outcomes=request.learning_outcomes,
            text_instructions=enhanced_instructions,
        )
    )

    planner_agent = CurriculumPlannerAgent(config, llm_provider)
    skeleton = planner_agent.run(
        CurriculumPlannerInput(
            context=context,
            num_modules=request.num_modules,
            sections_per_module=request.sections_per_module,
        )
    )
    return context, skeleton


def validate_prerequisites(
    skeleton, config: AgentConfig, llm_provider
):
    agent = PrerequisiteValidatorAgent(config, llm_provider)
    return agent.run(PrerequisiteValidatorInput(skeleton=skeleton))


def generate_sections(
    context, skeleton, request: GenerationRequestDTO, config: AgentConfig, llm_provider
) -> list[tuple]:
    """Run section_author → persona_adapter → content_block_generator per section."""
    all_sections: list[tuple] = []
    block_types = request.block_types

    for section_spec in skeleton.sections:
        author = SectionAuthorAgent(config, llm_provider)
        draft = author.run(
            SectionAuthorInput(
                section_spec=section_spec,
                context=context,
                skeleton=skeleton,
                block_types=block_types,
            )
        )

        adapter = PersonaAdapterAgent(config, llm_provider)
        adapted = adapter.run(
            PersonaAdapterInput(
                draft=draft,
                audience=request.audience,
                strategy=request.strategy,
            )
        )

        block_gen = ContentBlockGeneratorAgent(config, llm_provider)
        created = block_gen.run(
            ContentBlockGeneratorInput(
                section_spec=section_spec,
                adapted_section=adapted,
                context=context,
            )
        )

        all_sections.append((section_spec, adapted, created.blocks))

    return all_sections


def build_course(
    skeleton, all_sections: list[tuple], request: GenerationRequestDTO,
    context: GenerationContext | None = None,
    generation_iteration: int = 0,
) -> Course:
    """Assemble a Course entity from the skeleton and the generated sections.

    Optional `max_*` constraints truncate the build (post-LLM):
      - max_modules: cap on the number of modules
      - max_sections_per_module: cap on sections per module
      - max_blocks_per_section: cap on blocks per section

    If any `max_*` is None, that dimension is uncapped (LLM is free).
    If `context` is provided, the Course metadata is derived from it via
    Course.from_context(); otherwise the request DTO is used as a fallback.
    """
    max_modules = request.max_modules
    max_sections_per_module = request.max_sections_per_module
    max_blocks_per_section = request.max_blocks_per_section
    sections_per_module_hint = request.sections_per_module

    sorted_sections = sorted(skeleton.sections, key=lambda s: s.order)
    blocks_by_title = {spec.title: blocks for spec, _, blocks in all_sections}

    module_specs = list(skeleton.modules)
    if max_modules is not None:
        module_specs = module_specs[:max_modules]

    modules: list[Module] = []

    for module_idx, module_spec in enumerate(module_specs):
        if sections_per_module_hint is not None:
            start = module_idx * sections_per_module_hint
            end = start + sections_per_module_hint
            module_section_specs = sorted_sections[start:end]
        else:
            n = max(1, len(sorted_sections) // max(1, len(module_specs)))
            start = module_idx * n
            end = start + n if module_idx < len(module_specs) - 1 else len(sorted_sections)
            module_section_specs = sorted_sections[start:end]

        if max_sections_per_module is not None:
            module_section_specs = module_section_specs[:max_sections_per_module]

        module_id = new_module_id()
        module_sections: list[Section] = []

        for section_idx, section_spec in enumerate(module_section_specs):
            blocks = blocks_by_title.get(section_spec.title, tuple())
            if max_blocks_per_section is not None and len(blocks) > max_blocks_per_section:
                blocks = blocks[:max_blocks_per_section]
            section_id = new_section_id()
            blocks = tuple(
                ContentBlock(
                    id=b.id,
                    type=b.type,
                    order=i,
                    content=b.content,
                    estimated_time_minutes=b.estimated_time_minutes,
                    difficulty=b.difficulty,
                    created_at=b.created_at,
                    version=b.version,
                    parent_section_id=section_id,
                    parent_module_id=module_id,
                    block_index=i,
                )
                for i, b in enumerate(blocks)
            )
            module_sections.append(
                Section(
                    id=section_id,
                    title=section_spec.title,
                    order=section_idx,
                    learning_objectives=list(section_spec.learning_objectives),
                    blocks=blocks,
                    parent_module_id=module_id,
                    section_index=section_idx,
                    blocks_count=len(blocks),
                )
            )

        modules.append(
            Module(
                id=module_id,
                title=module_spec.title,
                order=module_spec.order,
                sections=tuple(module_sections),
                parent_course_id=None,
                module_index=module_idx,
                sections_count=len(module_sections),
                blocks_count=sum(len(s.blocks) for s in module_sections),
            )
        )

    if context is not None:
        course = Course.from_context(
            context,
            modules=tuple(modules),
        )
        course = Course(
            id=course.id,
            title=course.title,
            summary=course.summary,
            language=course.language,
            audience=course.audience,
            difficulty=course.difficulty,
            learning_outcomes=course.learning_outcomes,
            modules=course.modules,
            estimated_duration_minutes=course.estimated_duration_minutes,
            tags=course.tags,
            version=course.version,
            generation_iteration=generation_iteration,
            source_topic=course.source_topic,
        )
    else:
        course = Course(
            title=f"{request.topic} for {request.audience}",
            summary=(
                f"A {request.difficulty} course on {request.topic} "
                f"covering {', '.join(request.learning_outcomes)}"
            ),
            learning_outcomes=request.learning_outcomes,
            modules=tuple(modules),
            generation_iteration=generation_iteration,
            source_topic=request.topic,
        )

    course_id = course.id
    modules_with_parent = tuple(
        m if m.parent_course_id == course_id else Module(
            id=m.id,
            title=m.title,
            summary=m.summary,
            order=m.order,
            sections=m.sections,
            version=m.version,
            parent_course_id=course_id,
            module_index=m.module_index,
            sections_count=m.sections_count,
            blocks_count=m.blocks_count,
        )
        for m in course.modules
    )
    if not modules_with_parent or all(m.parent_course_id == course_id for m in modules_with_parent):
        return course.with_modules(modules_with_parent, course.version)
    return course.with_modules(modules_with_parent, course.version)


# ----------------------------------------------- #
# Phase 2: Evaluation                             #
# ----------------------------------------------- #

def evaluate_all(
    course: Course, all_sections: list[tuple], config: AgentConfig, llm_provider
):
    consistency_agent = ConsistencyCheckerAgent(config, llm_provider)
    consistency = consistency_agent.run(
        ConsistencyCheckerInput(sections=tuple(adapt for _, adapt, _ in all_sections))
    )

    eval_agent = EvaluatorAgent(config, llm_provider)
    report = eval_agent.run(EvaluatorInput(course=course, rubric_version="1.0.0"))

    return consistency, report


# ----------------------------------------------- #
# CLI I/O                                          #
# ----------------------------------------------- #

def prompt_feedback(prev: IterationResult | None) -> tuple[str, str]:
    """Ask the user for feedback. Returns (feedback_text, level). D-R3: level must be module/section/block."""
    print("\nOptions:")
    print("  [Enter] = auto-refine (auto-increase scope)")
    print("  '0'     = stop")
    print("  Or type custom feedback")
    try:
        text = input("> ").strip()
    except EOFError:
        return "", "module"

    if text == "0":
        return "0", "module"

    if not text:
        return text, "module"

    print("\nWhere should this feedback target?")
    print("  1) module (default)")
    print("  2) section")
    print("  3) block")
    try:
        choice = input("level> ").strip()
    except EOFError:
        choice = "1"

    level = {"2": "section", "3": "block"}.get(choice, "module")
    return text, level


def auto_feedback_decision(
    request: GenerationRequestDTO, prev: IterationResult | None
) -> GenerationRequestDTO:
    """Decide what to change when the user pressed Enter (auto-refine)."""
    if prev is None or prev.evaluation_passed:
        return request

    updates: dict[str, Any] = {}
    # Only nudge counts if they were set; if LLM-chooses, leave alone.
    if request.num_modules is not None:
        updates["num_modules"] = min(request.num_modules + 1, 5)
    if request.sections_per_module is not None:
        updates["sections_per_module"] = min(request.sections_per_module + 1, 3)

    # Diversify block types only if user specified a list. When LLM-chooses
    # block_types=None, the agents pick from the full taxonomy.
    if request.block_types is not None:
        additional_types = ["quiz", "key_points", "code", "summary", "check"]
        block_types = list(request.block_types)
        if len(block_types) < 5:
            for bt in additional_types:
                if bt not in block_types:
                    block_types.append(bt)
                    break
        updates["block_types"] = tuple(block_types)

    new_outcomes = ["Functions", "Loops", "Data Structures", "Error Handling", "Best Practices"]
    outcomes = list(request.learning_outcomes)
    for no in new_outcomes:
        if no not in outcomes:
            outcomes.append(no)
            break
    updates["learning_outcomes"] = tuple(outcomes)

    if not updates:
        return request
    request = request.model_copy(update=updates)
    print(
        f"\nAuto-increasing: modules={request.num_modules}, "
        f"sections/module={request.sections_per_module}, "
        f"types={request.block_types}"
    )
    return request


# CLI printer alias (canonical implementation in `cogenai.interfaces.cli.main`).
def _print_iteration_summary(result: IterationResult, verbose: bool = False) -> None:
    from cogenai.interfaces.cli.main import print_iteration_summary as _impl
    return _impl(result, verbose=verbose)


# Levels that don't require regenerating the structural skeleton or sections.
# When the only refinements were at these levels, the orchestrator can
# reuse the prior course and skip the expensive LLM-driven regeneration.
_SKELETON_PRESERVING_LEVELS = frozenset({"metadata"})
_SECTION_PRESERVING_LEVELS = frozenset({"metadata", "context"})


def _needs_skeleton_regen(
    prev_result: "IterationResult | None",
    working_bundle: "CourseBundle | None",
    last_refined: object | None,
) -> bool:
    """Return True iff the iteration must regenerate context + skeleton."""
    if working_bundle is None:
        return True
    if prev_result is not None and not prev_result.evaluation_passed:
        # Issues remain; assume we may need fresh context/skeleton.
        return True
    levels = _applied_levels(last_refined)
    if not levels:
        return True
    return any(level not in _SKELETON_PRESERVING_LEVELS for level in levels)


def _needs_section_regen(last_refined: object | None) -> bool:
    """Return True iff modules/sections were touched in the prior refinement.

    When only metadata/context changed, the prior course's modules are still
    valid; we can re-evaluate without re-running the LLM agents.
    """
    levels = _applied_levels(last_refined)
    if not levels:
        return True
    return any(level not in _SECTION_PRESERVING_LEVELS for level in levels)


def _applied_levels(last_refined: object | None) -> frozenset[str]:
    """Extract the set of refinement levels that were applied last iteration."""
    if last_refined is None:
        return frozenset()
    steps = getattr(last_refined, "steps_applied", ())
    return frozenset(getattr(s, "level", "") for s in steps if getattr(s, "level", ""))


# ----------------------------------------------- #
# Main orchestration                                #
# ----------------------------------------------- #

def run_demo(
    request: GenerationRequestDTO,
    *,
    auto: bool = False,
    verbose: bool = False,
    max_iterations: int | None = None,
    token_budget: int | None = None,
) -> tuple[Course, Any, int]:
    configure_logging()
    llm_provider = get_llm_provider()

    if not llm_provider.health_check():
        raise ValueError("LLM provider is not available")

    logger.info("LLM provider is available")

    policy = AgentAssignmentPolicy(
        default_model=get_settings().model or "stub",
        role_models=dict(request.agent_assignments or {}),
    )
    config = build_agent_config(assignments=policy)
    orchestrator = RefinerAgent(
        config=config,
        llm_provider=llm_provider,
        refiners=build_refiners(config, llm_provider),
    )

    updates: dict = {}
    if max_iterations is not None:
        updates["max_iterations"] = max_iterations
    if token_budget is not None:
        updates["token_budget"] = token_budget
    if updates:
        request = request.model_copy(update=updates)
    max_iter = request.max_iterations
    effective_token_budget = getattr(request, "token_budget", None)

    iteration = 0
    prev_result: IterationResult | None = None
    feedback_text = ""
    working_bundle: CourseBundle | None = None
    last_refined = None  # carries forward to detect which levels were applied

    while iteration < max_iter:
        iteration += 1
        logger.info(f"Iteration {iteration}/{max_iter}")

        needs_skeleton = _needs_skeleton_regen(prev_result, working_bundle, last_refined)
        if working_bundle is not None and not needs_skeleton:
            context = working_bundle.context
            skeleton = working_bundle.plan
            logger.debug("Reusing working_bundle context + skeleton")
        else:
            if working_bundle is not None and prev_result and not prev_result.evaluation_passed:
                logger.info("Re-running heavy LLM agents because issues remain")
            context, skeleton = generate_skeleton(
                request, config, llm_provider,
                feedback=feedback_text,
                prev_issues=prev_result.issues if prev_result else (),
            )
        # Skip expensive regeneration when the prior refinements only touched
        # levels that don't change the structural skeleton (e.g. metadata).
        if working_bundle is not None and not _needs_section_regen(last_refined):
            logger.debug("Reusing working_course (only metadata/context changed)")
            course = working_bundle.course
            all_sections = []
            prereq_report = validate_prerequisites(skeleton, config, llm_provider)
            consistency, report = evaluate_all(course, all_sections, config, llm_provider)
        else:
            prereq_report = validate_prerequisites(skeleton, config, llm_provider)
            all_sections = generate_sections(context, skeleton, request, config, llm_provider)
            course = build_course(
                skeleton, all_sections, request,
                context=context,
                generation_iteration=iteration,
            )
            consistency, report = evaluate_all(course, all_sections, config, llm_provider)

        logger.info(
            f"Evaluation: score={report.overall_score:.2f}, passed={report.passed}"
        )
        logger.info(f"Consistency: {consistency.passed}, Prerequisites: {prereq_report.passed}")

        result = IterationResult(
            iteration=iteration,
            course=course,
            evaluation_score=report.overall_score,
            evaluation_passed=report.passed,
            consistency_passed=consistency.passed,
            prerequisites_passed=prereq_report.passed,
            issues=report.issues,
            user_feedback=feedback_text,
        )
        _print_iteration_summary(result, verbose=verbose)

        if report.passed and consistency.passed and prereq_report.passed:
            logger.info("Course passed all checks!")
            print_final_course(course, report, iteration, verbose=verbose)
            return course, report, iteration

        if iteration >= max_iter:
            break

        if auto:
            request = auto_feedback_decision(request, result)
            feedback_text = "Make the course more comprehensive and engaging."
        else:
            feedback_text, _ = prompt_feedback(result)
            if feedback_text == "0":
                break

        refined = orchestrator.run(
            RefinerInput(
                course=CourseBundle(
                    course=course,
                    context=context,
                    plan=skeleton,
                    prerequisites=tuple(skeleton.prerequisites),
                ),
                evaluation_report=report,
                user_feedback=feedback_text if feedback_text else "",
            ),
            token_budget=effective_token_budget,
        )
        last_refined = refined
        logger.info(
            f"Refinement: applied={len(refined.steps_applied)}, "
            f"skipped={len(refined.steps_skipped)}, "
            f"notes={refined.refinement_notes}"
        )

        if isinstance(refined.revised, CourseBundle):
            working_bundle = refined.revised
        else:
            working_bundle = CourseBundle(
                course=refined.revised,
                context=context,
                plan=skeleton,
                prerequisites=tuple(skeleton.prerequisites),
            )

        prev_result = result

    # CLI printer lives in `cogenai.interfaces.cli.main` (Sprint 7).
    from cogenai.interfaces.cli.main import print_final_course as _print_final
    _print_final(course, report, iteration, verbose=verbose)
    return course, report, iteration
