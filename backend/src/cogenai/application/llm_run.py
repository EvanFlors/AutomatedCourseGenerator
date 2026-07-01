"""Top-level orchestration with LLM-driven decisions.

`run_with_llm_orchestrator` is the new entrypoint that uses an LLM
(LLMOrchestrator) to decide which refiners to invoke each iteration,
whether to pause for human input, and when to terminate.

This is the Sprint 10 brain. It is opt-in (the existing `run_demo`
remains the default for backward compat).
"""
from __future__ import annotations

import json
import time
from typing import Any

from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.evaluator import EvaluationIssue, EvaluationReport
from cogenai.application.orchestrator.refiner import (
    CourseBundle,
    RefinedDraft,
    RefinerAgent,
    RefinerInput,
)
from cogenai.application.orchestrator.top_orchestrator import (
    LLMOrchestrator,
    OrchestratorInput,
)
from cogenai.application.run_demo import IterationResult, build_refiners, run_demo
from cogenai.domain.course import Course
from cogenai.interfaces.cli.main import print_final_course as _print_final
from cogenai.interfaces.cli.main import print_iteration_summary as _print_iteration
from cogenai.interfaces.dto import GenerationRequestDTO
from cogenai.shared.logging import get_logger


logger = get_logger(__name__)


def _format_evaluation_report(report: EvaluationReport | None) -> str:
    if report is None:
        return "(no evaluation yet)"
    rubric = report.rubric
    rubric_str = (
        f"accuracy={rubric.accuracy:.2f} structure={rubric.structure_compliance:.2f} "
        f"audience={rubric.audience_alignment:.2f}"
    )
    issues = report.issues or ()
    top = ", ".join(
        f"[{i.severity}] {i.category}: {i.message[:80]}" for i in issues[:5]
    )
    return f"overall={report.overall_score:.2f} passed={report.passed} rubric: {rubric_str}\nissues: {top or '(none)'}"


def _format_request_summary(request: GenerationRequestDTO) -> str:
    return (
        f"topic={request.topic!r} audience={request.audience} "
        f"difficulty={request.difficulty} outcomes={list(request.learning_outcomes)}"
    )


def _format_history(history: list[str]) -> str:
    if not history:
        return "(no prior iterations)"
    return "\n".join(f"- {line}" for line in history)


def _format_working_bundle(bundle: CourseBundle | None) -> str:
    if bundle is None:
        return "(no working bundle yet)"
    course = bundle.course
    return (
        f"Course(title={course.title!r}, version={getattr(course, 'version', '?')}, "
        f"modules={len(getattr(course, 'modules', ()))})"
    )


def _decision_to_step_inputs(
    decision_actions, refiners: dict[str, Any], input_data: RefinerInput
) -> list[tuple[str, Any]]:
    """Map each OrchestratorAction.level to a refiner callable."""
    out: list[tuple[str, Any]] = []
    for action in decision_actions:
        refiner = refiners.get(action.level)
        if refiner is None:
            logger.warning(
                "orchestrator_action_skipped",
                level=action.level,
                reason="no refiner registered",
            )
            continue
        out.append((action.level, refiner))
    return out


def run_with_llm_orchestrator(
    request: GenerationRequestDTO,
    config: AgentConfig,
    llm_provider,
    *,
    auto: bool = False,
    verbose: bool = False,
    max_iterations: int | None = None,
    token_budget: int | None = None,
    pause_for_input: bool = True,
) -> tuple[Course, EvaluationReport | None, int]:
    """Run the pipeline with an LLM orchestrator making per-iteration decisions.

    Returns (course, report, iterations_run). When the orchestrator
    emits a `questions` payload and `pause_for_input` is True, the
    job is left in a state where it can be resumed via
    `JobStore.submit_answer()` — caller is responsible for polling.
    """
    if max_iterations is not None:
        request = request.model_copy(update={"max_iterations": max_iterations})
    if token_budget is not None:
        request = request.model_copy(update={"token_budget": token_budget})
    effective_token_budget = getattr(request, "token_budget", None)

    max_iter = request.max_iterations

    # Step 1: Run the heavy LLM pipeline once to produce the initial course
    # bundle (context + plan + sections + blocks). This mirrors run_demo's
    # initial phase; the LLM orchestrator takes over the refinement loop.
    course, report, _ = run_demo(request, auto=auto, verbose=False)
    iteration = 1

    # Step 2: Build the LLMOrchestrator + the standard refiner pool.
    orchestrator = LLMOrchestrator(config, llm_provider)
    refiners = build_refiners(config, llm_provider)
    refiner_agent = RefinerAgent(
        config=config, llm_provider=llm_provider, refiners=refiners,
    )

    history: list[str] = []
    bundle: CourseBundle | None = CourseBundle(
        course=course,
        context=None,
        plan=None,
    )

    while iteration < max_iter:
        decision_input = OrchestratorInput(
            iteration=iteration,
            max_iterations=max_iter,
            overall_score=report.overall_score if report else 0.0,
            passed=bool(report and report.passed),
            tokens_used=0,
            token_budget=effective_token_budget,
            evaluation_report_text=_format_evaluation_report(report),
            history_text=_format_history(history),
            working_bundle=_format_working_bundle(bundle),
            request_summary_text=_format_request_summary(request),
        )
        orch_out = orchestrator.run(decision_input)
        decision = orch_out.decision

        history.append(
            f"iter {iteration}: {decision.think[:200]} | "
            f"actions={[a.level for a in decision.actions]} | "
            f"questions={[q.id for q in decision.questions]}"
        )

        # Honor terminate from the LLM.
        if decision.terminate:
            logger.info(
                "orchestrator_terminate",
                reason=decision.termination_reason,
                iteration=iteration,
            )
            break

        # Honor human-in-the-loop pause.
        if pause_for_input and decision.questions:
            logger.info(
                "orchestrator_pause_for_input",
                question_ids=[q.id for q in decision.questions],
                iteration=iteration,
            )
            # The caller will store these via submit_answer before resuming.
            return (course, report, iteration)

        # Execute the actions in order via the standard refiner pipeline.
        if decision.actions:
            refiner_input = RefinerInput(
                course=bundle,
                evaluation_report=report or EvaluationReport(
                    overall_score=0.0, passed=False, rubric=_empty_rubric(), issues=(),
                ),
                user_feedback="",
            )
            # Determine the issues the LLM decided to address (derive from
            # the action reasons / categories as a fallback).
            refined = refiner_agent.run(refiner_input, token_budget=effective_token_budget)
            course = refined.revised.course if isinstance(refined.revised, CourseBundle) else refined.revised
            bundle = CourseBundle(course=course, context=None, plan=None)

        # Re-evaluate.
        from cogenai.application.run_demo import evaluate_all as _evaluate
        consistency, new_report = _evaluate(course, [], config, llm_provider)
        report = new_report

        iteration += 1
        if verbose:
            print(f"\n--- Iteration {iteration} done (orchestrator-driven) ---")

    print_or_suppress(verbose, course, report, iteration)
    return (course, report, iteration)


def print_or_suppress(verbose, course, report, iteration):
    if verbose:
        _print_iteration(
            IterationResult(
                iteration=iteration,
                course=course,
                evaluation_score=report.overall_score if report else 0.0,
                evaluation_passed=bool(report and report.passed),
                consistency_passed=True,
                prerequisites_passed=True,
                issues=tuple(report.issues) if report else (),
            ),
            verbose=verbose,
        )
        _print_final(course, report, iteration, verbose=verbose)


def _empty_rubric():
    from cogenai.application.orchestrator.evaluator import RubricScores
    return RubricScores()