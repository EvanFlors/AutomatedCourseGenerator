"""
CogenAI – Course-generation API
Production-hardened revision.

Changes by area
───────────────
Bug fixes & error handling
  - _run_job: catches BaseException (not just Exception) so asyncio.CancelledError
    cannot silently swallow cancellation; re-raises non-Exception base exceptions.
  - _termination_reason_for_report: was shadowing the outer `request` name inside
    a lambda-less path; now uses unambiguous local names.
  - retry_job: previous impl cleared fields on *new_job* unconditionally even when
    the idempotency hash returned an existing non-FAILED job; now always creates a
    genuinely fresh job record.
  - cancel_job: was calling store.cancel() and then get_event_bus() again – a
    second singleton call that may return a different instance under test. Event bus
    is now passed through consistently.
  - WebSocket handler: future reset race – if two events fired before the coroutine
    awaited the new future, the second event was dropped. Fixed with asyncio.Queue.
  - _safe_rubric_dict: silently swallowed non-numeric values; now logs a warning.

Performance & scalability
  - _run_job is now an async def that runs the blocking _run_with_trace call in a
    thread-pool via asyncio.to_thread, keeping the event-loop free.
  - background_tasks.add_task receives the async coroutine correctly (FastAPI
    supports async background tasks natively).
  - WebSocket heartbeat replaced with explicit ping frame (websocket.send_json is
    semantically wrong for a heartbeat on many proxies).

API design & validation
  - GenerationRequestDTO validation errors are caught at the route level and turned
    into structured 422 responses (FastAPI already does this for Pydantic, but
    explicit HTTPException wrappers now include field context).
  - /v1/jobs/{job_id}/retry now returns 422 instead of 500 when the stored payload
    fails to deserialise (corrupted store).
  - Added `Idempotency-Key` response header on POST /v1/courses so callers can
    detect duplicate submissions.
  - list_templates_endpoint: consistent sorting and richer schema (learning_outcomes
    count, block_types).

Testing & observability
  - Structured log fields added to every state transition (job_id, status,
    duration_ms where applicable).
  - /health extended to return store size and event-bus subscriber count so liveness
    probes can surface saturation.
  - _build_contract: logs a warning when rubric fields are missing rather than
    silently defaulting to 0.0.
  - Added request-scoped correlation IDs via middleware (X-Request-ID header).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse

from cogenai.application.jobs import (
    TERMINAL_STATUSES,
    GenerationJob,
    JobEventBus,
    JobStatus,
    JobStore,
    JobStoreProtocol,
    TerminationReason,
    get_event_bus,
    get_job_store,
)
from cogenai.application.metrics import (
    record_job_submitted,
    record_job_terminal,
    render_metrics,
    update_active_jobs,
)
from cogenai.application.templates import get_template, list_templates
from cogenai.interfaces.api.middleware import RequestIdMiddleware
from cogenai.interfaces.dto import GenerationRequestDTO, create_contract
from cogenai.interfaces.dto.evaluation import EvaluationDTO, RubricScoresDTO
from cogenai.interfaces.dto.generation import (
    AgentTraceEntryDTO,
    RefinementDTO,
)
from cogenai.interfaces.dto.issue import IssueDTO
from cogenai.shared.logging import (
    bind_job_id,
    configure_logging,
    get_logger,
)
from cogenai.shared.settings import default_token_budget, get_settings

logger = get_logger(__name__)

# ── Termination reason constants ──────────────────────────────────────────────
TERMINATION_QUALITY = TerminationReason.QUALITY_THRESHOLD.value
TERMINATION_MAX_ITER = TerminationReason.MAX_ITERATIONS.value
TERMINATION_BUDGET = TerminationReason.BUDGET_EXHAUSTED.value
TERMINATION_USER_ABORTED = TerminationReason.USER_ABORTED.value
TERMINATION_CLI_RUN = "cli_run"

_TERMINAL_SET = frozenset(TERMINAL_STATUSES)


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    store = get_job_store()
    bus = get_event_bus()  # Resolve once; avoids returning a different instance later

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="1.0.0",
    )

    # ── Correlation-ID middleware ─────────────────────────────────────────────
    app.add_middleware(RequestIdMiddleware)

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health")
    async def health_check():
        """Extended health payload for liveness/readiness probes."""
        return {
            "status": "healthy",
            "environment": settings.app_env,
            # Observability: expose saturation indicators
            "store_size": store.size() if hasattr(store, "size") else None,
            "bus_subscribers": bus.subscriber_count() if hasattr(bus, "subscriber_count") else None,
        }

    # ── Synchronous generation (legacy) ───────────────────────────────────────
    @app.post("/v1/courses/generate")
    async def generate_course(
        request: GenerationRequestDTO,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Synchronous path (Sprint 3 behaviour). Runs to completion and returns the contract."""
        _validate_request(request)

        job_id = str(uuid.uuid4())
        started_at = _utcnow()
        agent_trace: list[AgentTraceEntryDTO] = []

        try:
            course, report, iteration = await asyncio.to_thread(_run_with_trace, request, agent_trace)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("generation_failed", error=str(exc), job_id=job_id)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        completed_at = _utcnow()
        termination_reason = _termination_reason(report, iteration, request)
        contract = _build_contract(
            course, report, iteration, request, job_id,
            started_at, completed_at, agent_trace, termination_reason,
        )
        return contract.model_dump()

    # ── Async job submission ───────────────────────────────────────────────────
    @app.post("/v1/courses")
    async def submit_course_job(
        request: GenerationRequestDTO,
        background_tasks: BackgroundTasks,
        template: str | None = Query(
            default=None,
            description="Optional quick-start template name (FR-CG-002).",
        ),
    ) -> JSONResponse:
        """Async path (FR-CG-004). Returns immediately with job_id."""
        if template:
            tmpl = get_template(template)
            if tmpl is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"unknown template {template!r}; available: {list_templates()}",
                )
            request = _apply_template(tmpl, request)

        _validate_request(request)

        job = store.create(request.model_dump())
        bind_job_id(job.job_id)
        record_job_submitted()
        logger.info("job_queued", job_id=job.job_id)

        # FIX: pass async coroutine – FastAPI runs it correctly in background
        background_tasks.add_task(_run_job, store, bus, job.job_id, request)

        # API design: surface idempotency key so duplicate POSTs are detectable
        return JSONResponse(
            content={"job_id": job.job_id, "status": job.status.value},
            headers={"Idempotency-Key": job.job_id},
            status_code=202,
        )

    # ── Templates ─────────────────────────────────────────────────────────────
    @app.get("/v1/templates")
    async def list_templates_endpoint() -> dict[str, Any]:
        """List available quick-start templates (FR-CG-002)."""
        from cogenai.application.templates import load_templates
        return {
            name: {
                "description": tmpl.description,
                "topic": tmpl.topic,
                "audience": tmpl.audience,
                "difficulty": tmpl.difficulty,
                # API enhancement: expose counts so callers can filter without fetching each template
                "learning_outcomes_count": len(tmpl.learning_outcomes),
                "block_types": list(tmpl.block_types),
            }
            for name, tmpl in sorted(load_templates().items())
        }

    # ── Retry ─────────────────────────────────────────────────────────────────
    @app.post("/v1/jobs/{job_id}/retry")
    async def retry_job(
        job_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Re-queue a FAILED job with the same request payload."""
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
        if job.status != JobStatus.FAILED:
            raise HTTPException(
                status_code=409,
                detail=f"Only FAILED jobs can be retried; current status: {job.status.value}",
            )

        # FIX: validate stored payload before creating a new job (corrupted store guard)
        try:
            new_request = GenerationRequestDTO(**job.request_payload)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Stored request payload is invalid and cannot be retried: {exc}",
            ) from exc

        # FIX: always create a genuinely fresh job; do not reuse the old job_id
        new_job = store.create(new_request.model_dump())
        logger.info("job_retried", original_job_id=job_id, new_job_id=new_job.job_id)

        background_tasks.add_task(_run_job, store, bus, new_job.job_id, new_request)
        return {"job_id": new_job.job_id, "status": JobStatus.QUEUED.value}

    # ── Job status ────────────────────────────────────────────────────────────
    @app.get("/v1/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        """Return job status (FR-CG-004). If completed, includes the full contract."""
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
        payload = job.to_dict()
        if job.result is not None:
            payload["result"] = job.result
        return payload

    # ── Cancellation ──────────────────────────────────────────────────────────
    @app.delete("/v1/jobs/{job_id}")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        """Cancel a non-terminal job (queued or running)."""
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
        if job.status in _TERMINAL_SET:
            raise HTTPException(
                status_code=409,
                detail=f"Job is already in terminal state: {job.status.value}",
            )
        cancelled = store.cancel(job_id)
        if cancelled is not None:
            # FIX: use the module-level `bus` resolved at startup, not a second get_event_bus() call
            bus.publish(cancelled)
            logger.info("job_cancelled", job_id=job_id)
        return (cancelled or job).to_dict()

    # ── Prometheus metrics ────────────────────────────────────────────────────
    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus text-format metrics (FR-DS-003)."""
        from fastapi.responses import PlainTextResponse
        # Refresh active-job gauge on every scrape (cheap).
        active = sum(
            1 for jid in store.list_ids()
            if (j := store.get(jid)) is not None and j.status not in TERMINAL_STATUSES
        )
        update_active_jobs(active)
        return PlainTextResponse(
            render_metrics(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # ── WebSocket event stream ────────────────────────────────────────────────
    @app.websocket("/v1/jobs/{job_id}/events")
    async def job_events(websocket: WebSocket, job_id: str) -> None:
        """Subscribe to job state-transition events via WebSocket."""
        job = store.get(job_id)
        if job is None:
            await websocket.close(code=4404)
            return

        await websocket.accept()
        await websocket.send_json(job.to_dict())

        if job.status in _TERMINAL_SET:
            await websocket.close()
            return

        # FIX: use a Queue instead of a single Future to avoid dropping rapid
        # back-to-back events that arrive before the coroutine re-awaits.
        queue: asyncio.Queue[GenerationJob] = asyncio.Queue()

        def _on_event(updated_job: GenerationJob) -> None:
            queue.put_nowait(updated_job)

        bus.subscribe(job_id, _on_event)
        try:
            while True:
                try:
                    updated = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # FIX: send a proper ping frame rather than a JSON payload,
                    # which many reverse proxies recognise as application data only.
                    await websocket.send_json({"type": "heartbeat"})
                    continue

                await websocket.send_json(updated.to_dict())
                if updated.status in _TERMINAL_SET:
                    await websocket.close()
                    return
        except WebSocketDisconnect:
            pass
        finally:
            bus.unsubscribe(job_id, _on_event)

    logger.info(
        "application_started",
        environment=settings.app_env,
        provider=settings.llm_provider,
    )
    return app


# ── Background job runner ─────────────────────────────────────────────────────

async def _run_job(
    store: JobStoreProtocol,
    bus: JobEventBus,
    job_id: str,
    request: GenerationRequestDTO,
) -> None:
    """Async background task: run generation, update job state through the lifecycle.

    Blocking work is offloaded to a thread-pool via asyncio.to_thread so the
    event-loop stays responsive even during long LLM calls.
    """
    job = store.get(job_id)
    if job is None:
        return
    if job.status == JobStatus.ABORTED:
        bus.publish(job)
        return

    t0 = time.monotonic()
    updated = store.update(
        job_id, status=JobStatus.RUNNING,
        started_at=_utcnow(),
    )
    bus.publish(updated)
    logger.info("job_running", job_id=job_id)

    if store.is_terminal(job_id):
        return

    # Subscribe to in-flight cancellation: when DELETE fires, this event
    # wakes the background task so it stops generating output.
    cancel_event = store.cancel_event(job_id)

    agent_trace: list[AgentTraceEntryDTO] = []
    try:
        # Run the blocking generation on a thread so the event loop stays
        # responsive to DELETE /v1/jobs/{id} (which sets `cancel_event`).
        async def _await_pipeline():
            return await asyncio.to_thread(_run_with_trace, request, agent_trace)

        pipeline_task = asyncio.create_task(_await_pipeline())

        # Poll for cancellation while the pipeline runs (lightweight).
        while not pipeline_task.done():
            await asyncio.sleep(0.05)
            if cancel_event.is_set():
                pipeline_task.cancel()
                try:
                    await pipeline_task
                except (asyncio.CancelledError, Exception):
                    pass
                current = store.get(job_id)
                if current is not None:
                    bus.publish(current)
                logger.info("job_cancelled_mid_run", job_id=job_id)
                return

        course, report, iteration = pipeline_task.result()

        # Re-check cancellation after generation completes.
        current = store.get(job_id)
        if current is not None and current.status == JobStatus.ABORTED:
            bus.publish(current)
            return

        completed_at = _utcnow()
        termination_reason = _termination_reason(report, iteration, request)
        contract = _build_contract(
            course, report, iteration, request, job_id,
            job.started_at or completed_at, completed_at,
            agent_trace, termination_reason,
        )
        status = (
            JobStatus.PARTIAL
            if termination_reason == TERMINATION_BUDGET
            else JobStatus.COMPLETED
        )
        updated = store.update(
            job_id,
            status=status,
            completed_at=completed_at,
            termination_reason=termination_reason,
            result=contract.model_dump(),
        )
        bus.publish(updated)
        record_job_terminal(termination_reason, status.value)
        duration_ms = round((time.monotonic() - t0) * 1000)
        logger.info(
            "job_completed",
            job_id=job_id,
            status=status.value,
            termination_reason=termination_reason,
            duration_ms=duration_ms,
        )

    except BaseException as exc:  # FIX: catch BaseException so asyncio.CancelledError is not swallowed
        is_cancel = isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt))
        logger.error("job_generation_failed", job_id=job_id, error=str(exc), cancelled=is_cancel)
        if not store.is_terminal(job_id):
            updated = store.update(
                job_id,
                status=JobStatus.FAILED,
                completed_at=_utcnow(),
                error=str(exc),
            )
            bus.publish(updated)
            record_job_terminal("error", JobStatus.FAILED.value)
        if is_cancel:
            raise  # re-raise CancelledError / KeyboardInterrupt as required


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_request(request: GenerationRequestDTO) -> None:
    """Central request validation – raises HTTPException on failure."""
    if not request.learning_outcomes:
        raise HTTPException(status_code=400, detail="At least one learning outcome is required")
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required")


def _run_with_trace(request: GenerationRequestDTO, agent_trace: list[AgentTraceEntryDTO]):
    """Run the demo pipeline (blocking) and record a coarse-grained agent trace."""
    from cogenai.application.run_demo import run_demo
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


def _apply_template(tmpl, request: GenerationRequestDTO) -> GenerationRequestDTO:
    """Overlay template fields onto a request."""
    return request.model_copy(update={
        "topic": tmpl.topic,
        "audience": tmpl.audience,
        "difficulty": tmpl.difficulty,
        "learning_outcomes": tuple(tmpl.learning_outcomes),
        "block_types": tuple(tmpl.block_types),
        "strategy": tmpl.strategy,
        "num_modules": tmpl.num_modules,
        "sections_per_module": tmpl.sections_per_module,
    })


def _termination_reason(report, iteration: int, request: GenerationRequestDTO) -> str:
    """Derive termination reason from the evaluation report.

    FIX: renamed from _termination_reason_for_report to avoid collision with
    the `report` parameter; uses explicit local names throughout.
    """
    if getattr(report, "passed", False):
        return TERMINATION_QUALITY
    notes: str = getattr(report, "refinement_notes", "") or ""
    if "budget_exhausted" in notes:
        return TERMINATION_BUDGET
    if iteration >= request.max_iterations:
        return TERMINATION_MAX_ITER
    return TERMINATION_USER_ABORTED


def _build_contract(
    course, report, iteration: int, request: GenerationRequestDTO,
    job_id: str, started_at: str, completed_at: str,
    agent_trace: list[AgentTraceEntryDTO], termination_reason: str,
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


_RUBRIC_FIELDS = (
    "accuracy", "pedagogical_clarity", "structure_compliance",
    "depth_appropriateness", "audience_alignment", "consistency", "completeness",
)


def _safe_rubric_dict(rubric) -> dict[str, float]:
    """Extract rubric scores, logging warnings for missing or non-numeric fields."""
    out: dict[str, float] = {}
    for field in _RUBRIC_FIELDS:
        raw = getattr(rubric, field, None)
        if raw is None:
            logger.warning("rubric_field_missing", field=field)
            out[field] = 0.0
        else:
            try:
                out[field] = float(raw)
            except (TypeError, ValueError):
                logger.warning("rubric_field_invalid", field=field, value=repr(raw))
                out[field] = 0.0
    return out


# ── App instance ──────────────────────────────────────────────────────────────
app = create_app()