"""CLI surface for the CourseForge pipeline.

This module is the first-class entrypoint for the demo CLI. Invoke via:

    python -m cogenai.interfaces.cli --topic Python --iterations 2 --auto

The thin top-level `agent.py` shim forwards to `main()` here.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import Any

from cogenai.application.orchestrator.refiner import CourseBundle  # noqa: F401  (re-export)
from cogenai.application.run_demo import (
    IterationResult,
    auto_feedback_decision,
    prompt_feedback,
    run_demo,
)
from cogenai.domain.course import Course
from cogenai.interfaces.dto import create_contract
from cogenai.interfaces.dto.evaluation import EvaluationDTO, RubricScoresDTO
from cogenai.interfaces.dto.generation import RefinementDTO
from cogenai.interfaces.dto.generation_request import GenerationRequestDTO
from cogenai.interfaces.dto.issue import IssueDTO
from cogenai.shared.settings import get_settings
from cogenai.shared.settings import settings as _settings

__all__ = [
    "IterationResult",
    "main",
    "parse_args",
    "print_final_course",
    "print_iteration_summary",
    "prompt_feedback",
    "run_demo",
]


# ----------------------------------------------- #
# CLI printers                                     #
# ----------------------------------------------- #

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


def _course_to_dict(course, report, iteration, request: GenerationRequestDTO | None = None):
    """Serialize the final course using the same JSONOutputContract as the API."""
    settings_obj = get_settings()
    contract = create_contract(
        course, job_id=str(course.id), provider=settings_obj.llm_provider,
        model=settings_obj.model or "gpt-4",
    )
    contract.generation.completed_at = datetime.now(timezone.utc).isoformat()
    max_iter = request.max_iterations if request is not None else 3
    contract.generation.refinement = RefinementDTO(
        iterations=iteration, max_iterations=max_iter, termination_reason="cli_run",
    )
    rubric_dict = {
        f: float(getattr(report.rubric, f, 0.0) or 0.0)
        for f in (
            "accuracy", "pedagogical_clarity", "structure_compliance",
            "depth_appropriateness", "audience_alignment", "consistency", "completeness",
        )
    }
    contract.evaluation = EvaluationDTO(
        overall_score=report.overall_score,
        passed=report.passed,
        rubric=RubricScoresDTO(**rubric_dict),
        iteration_scores=[report.overall_score],
    )
    contract.issues = [
        IssueDTO(
            id=i.id, severity=i.severity, scope=i.scope, target_id=i.target_id,
            category=i.category, message=i.message, suggestion=i.suggestion,
            auto_fixable=i.auto_fixable,
        ) for i in report.issues
    ]
    return contract.model_dump()


# ----------------------------------------------- #
# CLI argument parsing                             #
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
        "--num-modules", type=int, default=None,
        help="Hint to the LLM (preferred module count)",
    )
    parser.add_argument(
        "--sections-per-module", type=int, default=None,
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
    parser.add_argument(
        "--assignment", action="append", default=None,
        metavar="ROLE=MODEL",
        help="Per-agent model assignment (FR-AG-014). Repeatable. "
             "Example: --assignment evaluator=gpt-4 --assignment refiner=gpt-4-mini",
    )
    return parser.parse_args(argv)


def _parse_assignment_args(values) -> dict[str, str] | None:
    """Parse --assignment role=model flags (repeatable)."""
    if not values:
        return None
    out: dict[str, str] = {}
    for v in values:
        if "=" not in v:
            raise argparse.ArgumentTypeError(
                f"--assignment must be ROLE=MODEL, got {v!r}"
            )
        role, _, model = v.partition("=")
        role = role.strip()
        model = model.strip()
        if not role or not model:
            raise argparse.ArgumentTypeError(
                f"--assignment must be ROLE=MODEL, got {v!r}"
            )
        out[role] = model
    return out or None


def _build_request_from_args(args: argparse.Namespace) -> GenerationRequestDTO:
    """Build a validated GenerationRequestDTO from parsed CLI args."""
    return GenerationRequestDTO(
        topic=args.topic,
        audience=args.audience,
        difficulty=args.difficulty,
        learning_outcomes=("Variables", "Data Types"),
        num_modules=args.num_modules or 1,
        sections_per_module=args.sections_per_module or 1,
        max_modules=args.max_modules,
        max_sections_per_module=args.max_sections_per_module,
        max_blocks_per_section=args.max_blocks_per_section,
        max_iterations=args.iterations,
        token_budget=_settings.default_token_budget(),
        agent_assignments=_parse_assignment_args(getattr(args, "assignment", None)),
    )


# ----------------------------------------------- #
# Main                                             #
# ----------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    request = _build_request_from_args(args)
    course, report, iteration = run_demo(request, auto=args.auto, verbose=args.verbose)
    if args.json:
        import json as _json
        payload = _course_to_dict(course, report, iteration, request=request)
        print(_json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())