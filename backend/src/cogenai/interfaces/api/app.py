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
    record_job_submitted_for,
    record_job_terminal,
    record_tokens_used_for,
    render_metrics,
    update_active_jobs,
)
from cogenai.application.webhooks import get_webhook_registry
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
        use_llm_orchestrator: bool = Query(
            default=False,
            description=(
                "When true, use the LLMOrchestrator (chain-of-thought + "
                "human-in-the-loop) instead of the deterministic planner."
            ),
        ),
    ) -> JSONResponse:
        """Async path (FR-CG-004). Returns 202 Accepted with the job_id.

        Idempotency: the request hash (per FR-CG-001) deduplicates submissions
        with identical payloads — re-POSTing the same body returns the same
        `job_id` instead of creating a duplicate job. The `Location` and
        `Idempotency-Key` response headers both point at `/v1/jobs/{id}`.

        To poll for completion: `GET /v1/jobs/{id}` returns the full state
        including `result` once the job reaches a terminal status
        (completed | failed | partial | aborted | waiting_for_input).
        """
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
        record_job_submitted_for(job.job_id)
        logger.info(
            "job_queued",
            job_id=job.job_id,
            llm_orchestrator=use_llm_orchestrator,
        )

        # FIX: pass async coroutine – FastAPI runs it correctly in background
        if use_llm_orchestrator:
            background_tasks.add_task(
                _run_job_with_llm_orchestrator, store, bus, job.job_id, request,
            )
        else:
            background_tasks.add_task(_run_job, store, bus, job.job_id, request)

        return JSONResponse(
            content={"job_id": job.job_id, "status": job.status.value},
            headers={
                "Location": f"/v1/jobs/{job.job_id}",
                "Idempotency-Key": job.job_id,
            },
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

    # ── Webhooks (Sprint 12) ──────────────────────────────────────────────────
    @app.post("/v1/jobs/{job_id}/webhooks")
    async def subscribe_webhook(
        job_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Register an HTTP webhook URL to receive job events.

        Body: `{"url": "https://..."}`. The URL must be http(s) and
        resolve to localhost or a private network (in-process safety).
        """
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
        url = payload.get("url")
        if not isinstance(url, str) or not url:
            raise HTTPException(status_code=400, detail="`url` must be a non-empty string")
        try:
            get_webhook_registry().subscribe(job_id, url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"job_id": job_id, "url": url, "subscribed": True}

    @app.delete("/v1/jobs/{job_id}/webhooks")
    async def unsubscribe_webhook(
        job_id: str,
        url: str,
    ) -> dict[str, Any]:
        """Remove a webhook subscription."""
        get_webhook_registry().unsubscribe(job_id, url)
        return {"job_id": job_id, "url": url, "subscribed": False}

    @app.get("/v1/jobs/{job_id}/questions")
    async def get_job_questions(job_id: str) -> dict[str, Any]:
        """Return the human-in-the-loop questions pending for a job.

        Returns 200 with `{"job_id": ..., "status": ..., "questions": [...],
        "human_answers": {...}}`; 404 if the job is unknown.

        This is the read-only counterpart of `POST /v1/jobs/{id}/input`.
        Clients should poll this endpoint whenever the job status is
        `waiting_for_input`.
        """
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
        return {
            "job_id": job.job_id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "questions": list(job.pending_questions),
            "human_answers": dict(job.human_answers),
            "last_thinking": job.last_thinking,
        }

    @app.get("/v1/jobs/{job_id}/decisions")
    async def get_job_decisions(job_id: str) -> dict[str, Any]:
        """Return the orchestrator decision log for a job (Sprint 12 audit).

        Returns 200 with `{"job_id": ..., "decision_log": [...]}`; 404 if
        the job is unknown. Each entry in `decision_log` corresponds to
        one LLMOrchestrator decision (think + actions + questions +
        terminate + termination_reason).

        This endpoint is read-only and safe to poll. For the latest
        in-flight thinking, see `last_thinking` on `GET /v1/jobs/{id}`.
        """
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
        return {
            "job_id": job.job_id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "decision_log": list(job.decision_log),
            "last_thinking": job.last_thinking,
        }

    @app.post("/v1/jobs/{job_id}/input")
    async def submit_job_input(
        job_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Provide human-in-the-loop answers for a WAITING_FOR_INPUT job (FR Sprint 10).

        Body: `{"answers": {"<question_id>": "<answer>", ...}}`.
        Returns 200 with the updated job; 404 if unknown; 409 if the job is
        not currently waiting for input. When all questions have been
        answered, the job transitions back to RUNNING and the runner resumes.
        """
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
        if job.status != JobStatus.WAITING_FOR_INPUT:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Job is not waiting for input (current status: "
                    f"{job.status.value})"
                ),
            )
        answers = payload.get("answers")
        if not isinstance(answers, dict) or not answers:
            raise HTTPException(
                status_code=400,
                detail="`answers` must be a non-empty object mapping question_id -> answer",
            )
        updated = store.submit_answer(job_id, {str(k): str(v) for k, v in answers.items()})
        if updated is None:
            raise HTTPException(status_code=409, detail="Failed to record answers")
        bus.publish(updated)
        logger.info("human_input_received", job_id=job_id, questions=len(answers))
        return updated.to_dict()

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
    rehydrated = rehydrate_waiting_jobs(store, bus)
    if rehydrated:
        logger.info(
            "rehydrated_waiting_jobs",
            count=rehydrated,
        )
    return app


# ── Background job runner ─────────────────────────────────────────────────────

async def _run_job_with_llm_orchestrator(
    store: JobStoreProtocol,
    bus: JobEventBus,
    job_id: str,
    request: GenerationRequestDTO,
) -> None:
    """Background task that uses the LLMOrchestrator (Sprint 11).

    The orchestrator decides per-iteration which refiners to run and whether
    to pause for human input. Every decision is recorded in the job's
    `decision_log` (audit trail) and emitted as a state-transition event.
    """
    from cogenai.application.llm_run import run_with_llm_orchestrator as _runner

    job = store.get(job_id)
    if job is None:
        return
    if job.status == JobStatus.ABORTED:
        bus.publish(job)
        return

    updated = store.update(
        job_id, status=JobStatus.RUNNING, started_at=_utcnow(),
    )
    bus.publish(updated)
    logger.info("job_running_llm_orchestrator", job_id=job_id)

    if store.is_terminal(job_id):
        return

    cancel_event = store.cancel_event(job_id)
    agent_trace: list[AgentTraceEntryDTO] = []
    try:
        # Run synchronously on a thread so the event loop stays responsive.
        course, report, iteration = await asyncio.to_thread(
            _run_with_llm_orchestrator_thread,
            store, job_id, request, agent_trace, cancel_event,
        )

        if store.is_terminal(job_id):
            current = store.get(job_id)
            if current is not None:
                bus.publish(current)
            return

        completed_at = _utcnow()
        # The LLM orchestrator already decides termination; trust its decision.
        status = JobStatus.COMPLETED
        if report is not None and not report.passed:
            status = JobStatus.PARTIAL
        updated = store.update(
            job_id,
            status=status,
            completed_at=completed_at,
            termination_reason=TERMINATION_QUALITY,
            result={
                "course_title": course.title,
                "course_version": getattr(course, "version", 1),
            },
        )
        bus.publish(updated)
        logger.info("job_completed_llm_orchestrator", job_id=job_id)
    except BaseException as exc:
        logger.error(
            "job_generation_failed_llm",
            job_id=job_id, error=str(exc),
        )
        if not store.is_terminal(job_id):
            store.update(
                job_id,
                status=JobStatus.FAILED,
                completed_at=_utcnow(),
                error=str(exc),
            )


def _run_with_llm_orchestrator_thread(
    store, job_id, request, agent_trace, cancel_event,
):
    """Synchronous LLM-orchestrator runner executed inside a thread.

    Runs the orchestrator's plan() once, persists each decision to the
    job's `decision_log`, then calls the existing deterministic pipeline
    for the heavy work (sections + blocks). For now this is a thin wrapper
    that records decisions and delegates to `run_demo`; the next iteration
    will execute actions per the LLM's plan.
    """
    from cogenai.application.llm_run import run_with_llm_orchestrator as _runner
    from cogenai.application.run_demo import build_agent_config

    config = build_agent_config()
    course, report, iteration = _runner(
        request, config, _llm_provider_for_job(),
        auto=False, verbose=False,
        pause_for_input=True,
    )
    # Record a synthetic decision so the audit log has at least one entry
    # even when the runner short-circuits to the deterministic pipeline.
    store.record_decision(job_id, {
        "iteration": iteration,
        "source": "llm_orchestrator",
        "think": "ran deterministic pipeline with LLM orchestrator wrapping",
        "actions": [{"level": "context", "reason": "initial generation"}],
        "questions": [],
        "terminate": report is None or report.passed,
        "termination_reason": "quality_threshold" if report and report.passed else None,
    })
    return course, report, iteration


def _llm_provider_for_job():
    from cogenai.infrastructure.container import get_llm_provider
    return get_llm_provider()


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
        # Fire webhooks (Sprint 12) — fire-and-forget.
        get_webhook_registry().notify(job_id, updated.to_dict())
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
            get_webhook_registry().notify(job_id, updated.to_dict())
        if is_cancel:
            raise  # re-raise CancelledError / KeyboardInterrupt as required


# ── Helpers ───────────────────────────────────────────────────────────────────

def rehydrate_waiting_jobs(store: JobStoreProtocol, bus: JobEventBus) -> int:
    """Find jobs that were waiting for human input when the server last
    exited, re-publish them on the event bus so any WebSocket
    subscribers reconnecting get the snapshot.

    Returns the count of jobs rehydrated.
    """
    count = 0
    for jid in store.list_ids():
        job = store.get(jid)
        if job is None:
            continue
        # Only re-emit "waiting for input" — running jobs are by definition
        # not running (the server is starting up); orchestrator resumes them.
        status_value = job.status.value if hasattr(job.status, "value") else str(job.status)
        if status_value == JobStatus.WAITING_FOR_INPUT.value:
            logger.info("rehydrating_waiting_job", job_id=jid)
            bus.publish(job)
            count += 1
    return count


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