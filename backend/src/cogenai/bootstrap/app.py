import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException

from cogenai.bootstrap import default_token_budget, get_settings
from cogenai.bootstrap.jobs import (
    GenerationJob,
    JobStatus,
    JobStore,
    JobStoreProtocol,
    TerminationReason,
    get_job_store,
)
from cogenai.bootstrap.logging import configure_logging, get_logger
from cogenai.interfaces.dto import GenerationRequestDTO, create_contract
from cogenai.interfaces.dto.evaluation import EvaluationDTO, RubricScoresDTO
from cogenai.interfaces.dto.generation import (
    AgentTraceEntryDTO,
    RefinementDTO,
)
from cogenai.interfaces.dto.issue import IssueDTO

logger = get_logger(__name__)


# Termination reason vocabulary aliases (kept for backward compat with Sprint 3).
TERMINATION_QUALITY = TerminationReason.QUALITY_THRESHOLD.value
TERMINATION_MAX_ITER = TerminationReason.MAX_ITERATIONS.value
TERMINATION_BUDGET = TerminationReason.BUDGET_EXHAUSTED.value
TERMINATION_USER_ABORTED = TerminationReason.USER_ABORTED.value
TERMINATION_CLI_RUN = "cli_run"


def create_app() -> FastAPI:

    configure_logging()
    settings = get_settings()
    store = get_job_store()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="1.0.0",
    )

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "environment": settings.app_env}

    @app.post("/v1/courses/generate")
    async def generate_course(
        request: GenerationRequestDTO,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Synchronous path (Sprint 3 behavior). Runs to completion and returns the contract.

        For the async lifecycle, prefer POST /v1/courses which returns immediately
        with a job_id, and GET /v1/jobs/{job_id} to poll status.
        """
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

        contract = _build_contract(
            course, report, iteration, request, job_id,
            started_at, completed_at, agent_trace, termination_reason,
        )
        return contract.model_dump()

    @app.post("/v1/courses")
    async def submit_course_job(
        request: GenerationRequestDTO,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Async path (FR-CG-004). Returns immediately with job_id."""
        if not request.learning_outcomes:
            raise HTTPException(status_code=400, detail="At least one learning outcome is required")
        if not request.topic.strip():
            raise HTTPException(status_code=400, detail="Topic is required")

        job = store.create(request.model_dump())
        background_tasks.add_task(_run_job, store, job.job_id, request)
        return {"job_id": job.job_id, "status": job.status.value}

    @app.get("/v1/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        """Return job status (FR-CG-004). If completed, includes the full contract."""
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"job {job_id} not found")
        payload = job.to_dict()
        if job.result is not None:
            payload["result"] = job.result
        return payload

    @app.delete("/v1/jobs/{job_id}")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        """Mark a queued or running job as aborted (Sprint 5).

        For jobs already in a terminal state, returns 409 Conflict.
        """
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"job {job_id} not found")
        if job.status in (
            JobStatus.COMPLETED, JobStatus.FAILED,
            JobStatus.PARTIAL, JobStatus.ABORTED,
        ):
            raise HTTPException(
                status_code=409,
                detail=f"job is in terminal state {job.status.value!r}",
            )
        from datetime import datetime, timezone
        store.update(
            job_id,
            status=JobStatus.ABORTED,
            completed_at=datetime.now(timezone.utc).isoformat(),
            termination_reason=TERMINATION_USER_ABORTED,
        )
        return {"job_id": job_id, "status": JobStatus.ABORTED.value}

    logger.info(
        "application_started",
        environment=settings.app_env,
        provider=settings.llm_provider,
    )
    return app


def _run_job(store: JobStoreProtocol, job_id: str, request: GenerationRequestDTO) -> None:
    """Background task: run generation, update job state through the lifecycle.

    If the job was cancelled (`DELETE /v1/jobs/{id}`) before we started
    or while running, leave the aborted state intact and skip result
    persistence. Per FR-AG-010 the status stays 'aborted' and the
    cancellation is treated as authoritative.
    """
    job = store.get(job_id)
    if job is None:
        return
    if job.status == JobStatus.ABORTED:
        return
    store.update(job_id, status=JobStatus.RUNNING, started_at=datetime.now(timezone.utc).isoformat())
    agent_trace: list[AgentTraceEntryDTO] = []
    try:
        course, report, iteration = _run_with_trace(request, agent_trace)
        # Re-check abort after generation completes.
        current = store.get(job_id)
        if current is not None and current.status == JobStatus.ABORTED:
            return
        completed_at = datetime.now(timezone.utc).isoformat()
        termination_reason = _termination_reason_for_report(report, iteration, request)
        contract = _build_contract(
            course, report, iteration, request, job_id,
            job.started_at or completed_at, completed_at,
            agent_trace, termination_reason,
        )
        # If termination reason is budget_exhausted, status is "partial" (FR-AG-010).
        status = (
            JobStatus.PARTIAL
            if termination_reason == TERMINATION_BUDGET
            else JobStatus.COMPLETED
        )
        store.update(
            job_id,
            status=status,
            completed_at=completed_at,
            termination_reason=termination_reason,
            result=contract.model_dump(),
        )
    except Exception as exc:
        logger.error("job_generation_failed", job_id=job_id, error=str(exc))
        store.update(
            job_id,
            status=JobStatus.FAILED,
            completed_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
        )


def _run_with_trace(request, agent_trace):
    """Run the demo pipeline and record a coarse-grained agent trace.

    Returns (course, report, iteration).
    """
    from cogenai.bootstrap.orchestrator import run_demo
    request = request.model_copy(update={
        "token_budget": request.effective_token_budget(default_token_budget()),
    })
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


def _build_contract(
    course, report, iteration, request, job_id,
    started_at, completed_at, agent_trace, termination_reason,
):
    settings = get_settings()
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
    return contract


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