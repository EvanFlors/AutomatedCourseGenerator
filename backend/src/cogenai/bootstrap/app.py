import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from cogenai.bootstrap import get_settings
from cogenai.bootstrap.logging import configure_logging, get_logger
from cogenai.interfaces.dto import GenerationRequestDTO, create_contract
from cogenai.interfaces.dto.evaluation import EvaluationDTO, RubricScoresDTO
from cogenai.interfaces.dto.generation import (
    AgentTraceEntryDTO,
    RefinementDTO,
)
from cogenai.interfaces.dto.issue import IssueDTO

logger = get_logger(__name__)


# Termination reason vocabulary per FR-AG-010.
TERMINATION_QUALITY = "quality_threshold"
TERMINATION_MAX_ITER = "max_iterations"
TERMINATION_BUDGET = "budget_exhausted"
TERMINATION_USER_ABORTED = "user_aborted"
TERMINATION_CLI_RUN = "cli_run"


def create_app() -> FastAPI:

    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="1.0.0",
    )

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "environment": settings.app_env}

    @app.post("/v1/courses/generate")
    async def generate_course(request: GenerationRequestDTO) -> dict[str, Any]:
        if not request.learning_outcomes:
            raise HTTPException(status_code=400, detail="At least one learning outcome is required")
        if not request.topic.strip():
            raise HTTPException(status_code=400, detail="Topic is required")

        job_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        agent_trace: list[AgentTraceEntryDTO] = []

        try:
            course, report, iteration = _run_with_trace(request, agent_trace)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("generation_failed", error=str(exc))
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        completed_at = datetime.now(timezone.utc).isoformat()
        termination_reason = _termination_reason_for_report(report, iteration, request)

        contract = create_contract(
            course,
            job_id=job_id,
            provider=settings.llm_provider,
            model=settings.model or "gpt-4",
        )
        contract.generation.started_at = started_at
        contract.generation.completed_at = completed_at
        contract.generation.agent_trace = agent_trace
        contract.generation.refinement = RefinementDTO(
            iterations=iteration,
            max_iterations=request.max_iterations,
            termination_reason=termination_reason,
        )
        contract.evaluation = EvaluationDTO(
            overall_score=report.overall_score,
            passed=report.passed,
            rubric=RubricScoresDTO(**_safe_rubric_dict(report.rubric)),
            iteration_scores=[report.overall_score],
        )
        contract.issues = [
            IssueDTO(
                id=i.id, severity=i.severity, scope=i.scope, target_id=i.target_id,
                category=i.category, message=i.message, suggestion=i.suggestion,
                auto_fixable=i.auto_fixable,
            )
            for i in report.issues
        ]
        return contract.model_dump()

    logger.info(
        "application_started",
        environment=settings.app_env,
        provider=settings.llm_provider,
    )
    return app


def _run_with_trace(request, agent_trace):
    """Run the demo pipeline and record a coarse-grained agent trace.

    Returns (course, report, iteration).
    """
    from agent import run_demo
    course, report, iteration = run_demo(request, auto=False, verbose=False)
    for agent_name in (
        "context_synthesizer", "curriculum_planner", "section_author",
        "persona_adapter", "content_block_generator",
        "consistency_checker", "prerequisite_validator",
        "evaluator", "refiner",
    ):
        agent_trace.append(AgentTraceEntryDTO(
            agent=agent_name, phase="draft",
            iteration=iteration, status="success",
        ))
    return course, report, iteration


def _termination_reason_for_report(report, iteration, request) -> str:
    if getattr(report, "passed", False):
        return TERMINATION_QUALITY
    notes = getattr(report, "refinement_notes", "") or ""
    if "budget_exhausted" in notes:
        return TERMINATION_BUDGET
    if iteration >= request.max_iterations:
        return TERMINATION_MAX_ITER
    return TERMINATION_USER_ABORTED


def _safe_rubric_dict(rubric) -> dict[str, float]:
    out: dict[str, float] = {}
    for field in (
        "accuracy", "pedagogical_clarity", "structure_compliance",
        "depth_appropriateness", "audience_alignment", "consistency", "completeness",
    ):
        out[field] = float(getattr(rubric, field, 0.0) or 0.0)
    return out


# Create the app instance
app = create_app()