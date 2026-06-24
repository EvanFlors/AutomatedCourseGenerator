from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any

from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.consistency_checker import (
    ConsistencyCheckerAgent,
    ConsistencyCheckerInput,
)
from cogenai.agents_implementations.content_block_generator import (
    ContentBlockGeneratorAgent,
    ContentBlockGeneratorInput,
)
from cogenai.agents_implementations.context_synthesizer import (
    ContextSynthesizerAgent,
    ContextSynthesizerInput,
    GenerationContext,
)
from cogenai.agents_implementations.curriculum_planner import (
    CurriculumPlannerAgent,
    CurriculumPlannerInput,
)
from cogenai.agents_implementations.evaluator import EvaluatorAgent, EvaluatorInput
from cogenai.agents_implementations.persona_adapter import (
    PersonaAdapterAgent,
    PersonaAdapterInput,
)
from cogenai.agents_implementations.prerequisite_validator import (
    PrerequisiteValidatorAgent,
    PrerequisiteValidatorInput,
)
from cogenai.agents_implementations.refiner import CourseBundle, RefinerAgent, RefinerInput
from cogenai.agents_implementations.refiners import (
    BlockRefinerAgent,
    ContextRefinerAgent,
    MetadataRefinerAgent,
    ModuleRefinerAgent,
    PlanRefinerAgent,
    PrerequisitesRefinerAgent,
    SectionRefinerAgent,
)
from cogenai.agents_implementations.section_author import (
    SectionAuthorAgent,
    SectionAuthorInput,
)
from cogenai.bootstrap import get_settings
from cogenai.bootstrap.container import get_llm_provider
from cogenai.bootstrap.logging import configure_logging, get_logger
from cogenai.domain.course.entities import ContentBlock, Course, Module, Section
from cogenai.domain.shared.value_objects import new_module_id, new_section_id
from cogenai.interfaces.dto.generation_request import GenerationRequestDTO

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


def build_agent_config(model_name: str | None = None) -> AgentConfig:
    settings = get_settings()
    return AgentConfig.default(model_name=model_name or settings.model or "stub")


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

    updates: dict[str, Any] = {
        "num_modules": min(request.num_modules + 1, 5),
        "sections_per_module": min(request.sections_per_module + 1, 3),
    }

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

    request = request.model_copy(update=updates)
    print(
        f"\nAuto-increasing: modules={request.num_modules}, "
        f"sections/module={request.sections_per_module}, "
        f"types={request.block_types}"
    )
    return request


def print_iteration_summary(result: IterationResult, verbose: bool = False) -> None:
    print(f"\n{'=' * 50}")
    print(f"Iteration {result.iteration} Results:")
    print(f"  Score:           {result.evaluation_score:.2f}  (passed: {result.evaluation_passed})")
    print(f"  Consistency:     {result.consistency_passed}")
    print(f"  Prerequisites:   {result.prerequisites_passed}")
    print(f"  Course version:  {result.course.version}")
    print(f"  Gen iteration:   {result.course.generation_iteration}")
    print(f"  Title:           {result.course.title}")
    if verbose:
        print(f"  Source topic:    {result.course.source_topic}")
        print(f"  Summary:         {result.course.summary[:80]}")
        if result.course.audience:
            print(f"  Audience:        {result.course.audience.profile}")
        if result.course.difficulty:
            print(f"  Difficulty:      {result.course.difficulty.level}")
        print(f"  Outcomes:        {', '.join(result.course.learning_outcomes)}")
    print(f"  Modules:         {len(result.course.modules)}")
    total_sections = sum(len(m.sections) for m in result.course.modules)
    total_blocks = sum(
        len(s.blocks) for m in result.course.modules for s in m.sections
    )
    print(f"  Sections/Modules:{total_sections}")
    print(f"  Blocks:          {total_blocks}")
    if result.issues:
        print(f"\nTop issues:")
        for issue in result.issues[:5]:
            print(f"  - [{issue.severity}] {issue.category}: {issue.message[:120]}")
    print("=" * 50)


# ----------------------------------------------- #
# Main orchestration                                #
# ----------------------------------------------- #

def run_demo(
    request: GenerationRequestDTO,
    *,
    auto: bool = False,
    verbose: bool = False,
    max_iterations: int | None = None,
) -> tuple[Course, Any, int]:
    configure_logging()
    llm_provider = get_llm_provider()

    if not llm_provider.health_check():
        raise ValueError("LLM provider is not available")

    logger.info("LLM provider is available")

    config = build_agent_config()
    orchestrator = RefinerAgent(
        config=config,
        llm_provider=llm_provider,
        refiners=build_refiners(config, llm_provider),
    )

    if max_iterations is not None:
        request = request.model_copy(update={"max_iterations": max_iterations})
    max_iter = request.max_iterations

    iteration = 0
    prev_result: IterationResult | None = None
    feedback_text = ""
    feedback_level = "module"
    working_bundle: CourseBundle | None = None

    while iteration < max_iter:
        iteration += 1
        logger.info(f"Iteration {iteration}/{max_iter}")

        if working_bundle is not None:
            context = working_bundle.context
            skeleton = working_bundle.plan
            if prev_result and not prev_result.evaluation_passed:
                logger.info("Re-running heavy LLM agents because issues remain")
                context, skeleton = generate_skeleton(
                    request, config, llm_provider,
                    feedback=feedback_text,
                    prev_issues=prev_result.issues if prev_result else (),
                )
        else:
            context, skeleton = generate_skeleton(
                request, config, llm_provider,
                feedback=feedback_text,
                prev_issues=prev_result.issues if prev_result else (),
            )
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
        print_iteration_summary(result, verbose=verbose)

        if report.passed and consistency.passed and prereq_report.passed:
            logger.info("Course passed all checks!")
            print_final_course(course, report, iteration, verbose=verbose)
            return course, report, iteration

        if iteration >= max_iter:
            break

        if auto:
            request = auto_feedback_decision(request, result)
            feedback_text = "Make the course more comprehensive and engaging."
            feedback_level = "module"
        else:
            feedback_text, feedback_level = prompt_feedback(result)
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
            )
        )
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

    print_final_course(course, report, iteration, verbose=verbose)
    return course, report, iteration


def print_final_course(course: Course, report, iteration: int, verbose: bool = False) -> None:
    print(f"\n{'=' * 50}")
    print("FINAL COURSE")
    print("=" * 50)
    print(f"Title:           {course.title}")
    print(f"Summary:         {course.summary}")
    print(f"Audience:        {course.audience.profile if course.audience else 'n/a'}")
    print(f"Difficulty:      {course.difficulty.level if course.difficulty else 'n/a'}")
    print(f"Outcomes:        {', '.join(course.learning_outcomes)}")
    print(f"Source topic:    {course.source_topic}")
    print(f"Course version:  {course.version}")
    print(f"Gen iteration:   {course.generation_iteration}")
    print(f"Modules:         {len(course.modules)}")
    for module in course.modules:
        sec_str = ", ".join(
            f"{s.title} ({len(s.blocks)} blocks)" for s in module.sections
        )
        print(
            f"  - {module.title}  [idx={module.module_index}, "
            f"sections={module.sections_count}, blocks={module.blocks_count}]"
        )
        if verbose:
            for section in module.sections:
                print(
                    f"      * {section.title}  [idx={section.section_index}, "
                    f"blocks={section.blocks_count}, parent_module={section.parent_module_id}]"
                )
                for block in section.blocks:
                    print(
                        f"        - {block.type}  [idx={block.block_index}, "
                        f"parent_section={block.parent_section_id}, "
                        f"parent_module={block.parent_module_id}]"
                    )
    print(f"\nFinal score:  {report.overall_score:.2f}  (passed: {report.passed})")
    print(f"Iterations:   {iteration}")


def _course_to_dict(course: Course, report, iteration: int) -> dict:
    return {
        "schema_version": "1.0.0",
        "title": course.title,
        "summary": course.summary,
        "audience": course.audience.profile if course.audience else None,
        "difficulty": course.difficulty.level if course.difficulty else None,
        "learning_outcomes": list(course.learning_outcomes),
        "source_topic": course.source_topic,
        "course_version": course.version,
        "generation_iteration": course.generation_iteration,
        "modules": [
            {
                "id": str(m.id),
                "title": m.title,
                "order": m.order,
                "module_index": m.module_index,
                "sections_count": m.sections_count,
                "blocks_count": m.blocks_count,
                "sections": [
                    {
                        "id": str(s.id),
                        "title": s.title,
                        "order": s.order,
                        "section_index": s.section_index,
                        "blocks_count": s.blocks_count,
                        "parent_module_id": str(s.parent_module_id) if s.parent_module_id else None,
                        "learning_objectives": list(s.learning_objectives),
                        "blocks": [
                            {
                                "id": str(b.id),
                                "type": b.type,
                                "order": b.order,
                                "block_index": b.block_index,
                                "parent_section_id": str(b.parent_section_id) if b.parent_section_id else None,
                                "parent_module_id": str(b.parent_module_id) if b.parent_module_id else None,
                                "content": b.content,
                            }
                            for b in s.blocks
                        ],
                    }
                    for s in m.sections
                ],
            }
            for m in course.modules
        ],
        "evaluation": {
            "overall_score": report.overall_score,
            "passed": report.passed,
        },
        "iterations": iteration,
    }


# ----------------------------------------------- #
# CLI entrypoint                                    #
# ----------------------------------------------- #

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CourseForge demo CLI (multi-agent refinement pipeline)",
    )
    parser.add_argument(
        "--topic", default="Python", help="Course topic"
    )
    parser.add_argument(
        "--audience", default="beginner",
        choices=["beginner", "professional", "engineer", "architect", "manager", "researcher", "student"],
    )
    parser.add_argument(
        "--difficulty", default="beginner",
        choices=["beginner", "intermediate", "advanced", "expert"],
    )
    parser.add_argument(
        "--iterations", type=int, default=3,
        help="Max refinement iterations",
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Skip interactive prompts; auto-increase scope and feedback each iteration",
    )
    parser.add_argument(
        "--num-modules", type=int, default=1,
        help="Hint to the LLM (preferred module count)",
    )
    parser.add_argument(
        "--sections-per-module", type=int, default=1,
        help="Hint to the LLM (preferred sections per module)",
    )
    parser.add_argument(
        "--max-modules", type=int, default=None,
        help="Hard cap on modules (overrides LLM output)",
    )
    parser.add_argument(
        "--max-sections-per-module", type=int, default=None,
        help="Hard cap on sections per module (overrides LLM output)",
    )
    parser.add_argument(
        "--max-blocks-per-section", type=int, default=None,
        help="Hard cap on blocks per section (overrides LLM output)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print full per-block metadata for every module/section/block",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit the final course as a single-line JSON object",
    )
    return parser.parse_args(argv)


def _build_request_from_args(args: argparse.Namespace) -> GenerationRequestDTO:
    """Build a validated GenerationRequestDTO from parsed CLI args."""
    return GenerationRequestDTO(
        topic=args.topic,
        audience=args.audience,
        difficulty=args.difficulty,
        learning_outcomes=("Variables", "Data Types"),
        num_modules=args.num_modules,
        sections_per_module=args.sections_per_module,
        max_modules=args.max_modules,
        max_sections_per_module=args.max_sections_per_module,
        max_blocks_per_section=args.max_blocks_per_section,
        max_iterations=args.iterations,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    request = _build_request_from_args(args)

    course, report, iteration = run_demo(request, auto=args.auto, verbose=args.verbose)
    if args.json:
        import json as _json
        print(_json.dumps(_course_to_dict(course, report, iteration)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
