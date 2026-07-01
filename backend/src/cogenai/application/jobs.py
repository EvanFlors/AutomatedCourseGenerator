"""Async job lifecycle (FR-CG-004, FR-AG-010).

Provides:
- `JobStatus` enum: queued | running | completed | failed | partial | aborted
- `TerminationReason` vocab: quality_threshold | max_iterations | budget_exhausted | user_aborted
- `GenerationJob`: holds request + status + result + timestamps
- `JobStore` (in-memory) and `SqliteJobStore` (persistent); both expose the
  same interface. Idempotency on request hash (FR-CG-001).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol
import contextlib


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    ABORTED = "aborted"


# Terminal statuses (no further transitions allowed)
TERMINAL_STATUSES = frozenset({
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.PARTIAL,
    JobStatus.ABORTED,
})


class TerminationReason(str, Enum):
    QUALITY_THRESHOLD = "quality_threshold"
    MAX_ITERATIONS = "max_iterations"
    BUDGET_EXHAUSTED = "budget_exhausted"
    USER_ABORTED = "user_aborted"


@dataclass
class GenerationJob:
    job_id: str
    request_id: str
    request_payload: dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    termination_reason: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    # Human-in-the-loop: questions pending answer, and answers received.
    pending_questions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    human_answers: dict[str, str] = field(default_factory=dict)
    last_thinking: str = ""
    # Audit trail: one entry per LLMOrchestrator decision (Sprint 11).
    decision_log: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "request_id": self.request_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "termination_reason": self.termination_reason,
            "error": self.error,
            "has_result": self.result is not None,
            "pending_questions": list(self.pending_questions),
            "human_answers": dict(self.human_answers),
            "last_thinking": self.last_thinking,
            "decision_log": list(self.decision_log),
        }


def compute_request_id(payload: dict[str, Any]) -> str:
    """Stable hash for idempotency per FR-CG-001."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class JobStoreProtocol(Protocol):
    """Interface both `JobStore` and `SqliteJobStore` implement."""

    def create(self, request_payload: dict[str, Any]) -> GenerationJob: ...
    def get(self, job_id: str) -> GenerationJob | None: ...
    def update(self, job_id: str, **fields: Any) -> GenerationJob: ...
    def list_ids(self) -> list[str]: ...
    def clear(self) -> None: ...
    def cancel(self, job_id: str) -> GenerationJob | None: ...
    def is_terminal(self, job_id: str) -> bool: ...
    def is_cancelled(self, job_id: str) -> bool: ...
    def submit_answer(self, job_id: str, answers: dict[str, str]) -> GenerationJob | None: ...
    def record_decision(self, job_id: str, decision: dict[str, Any]) -> GenerationJob | None: ...


class JobStore:
    """Thread-safe in-memory store keyed by job_id, with idempotency by request_id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, GenerationJob] = {}
        self._by_request: dict[str, str] = {}
        # Threading.Event per job: set() when DELETE /v1/jobs/{id} fires.
        # Background tasks wait on this with a timeout to support prompt
        # mid-run cancellation.
        self._cancel_events: dict[str, threading.Event] = {}

    def create(self, request_payload: dict[str, Any]) -> GenerationJob:
        request_id = compute_request_id(request_payload)
        with self._lock:
            existing_id = self._by_request.get(request_id)
            if existing_id is not None:
                return self._jobs[existing_id]
            job_id = str(uuid.uuid4())
            job = GenerationJob(
                job_id=job_id,
                request_id=request_id,
                request_payload=request_payload,
            )
            self._jobs[job_id] = job
            self._by_request[request_id] = job_id
            return job

    def get(self, job_id: str) -> GenerationJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields: Any) -> GenerationJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(f"job {job_id} not found")
            for key, value in fields.items():
                if not hasattr(job, key):
                    raise AttributeError(f"GenerationJob has no field {key!r}")
                setattr(job, key, value)
            return job

    def cancel(self, job_id: str) -> GenerationJob | None:
        """Mark a non-terminal job as ABORTED. Returns the updated job, or None.

        Returns None if the job is already in a terminal state (no-op).
        Returns None if the job_id is unknown.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status in TERMINAL_STATUSES:
                return None
            job.status = JobStatus.ABORTED
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.termination_reason = TerminationReason.USER_ABORTED.value
            # Wake up any background task that's polling for cancellation.
            event = self._cancel_events.get(job_id)
            if event is not None:
                event.set()
            return job

    def is_terminal(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            return job.status in TERMINAL_STATUSES

    def record_decision(
        self, job_id: str, decision: dict[str, Any]
    ) -> GenerationJob | None:
        """Append an orchestrator decision to the audit trail.

        `decision` should be a JSON-serializable dict, e.g.
        `{"iteration": 2, "think": "...", "actions": [...], "questions": [...]}`.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            log = list(job.decision_log) + [decision]
            job.decision_log = tuple(log)
            if decision.get("think"):
                job.last_thinking = decision["think"]
            return job

    def submit_answer(
        self, job_id: str, answers: dict[str, str]
    ) -> GenerationJob | None:
        """Record human answers for a WAITING_FOR_INPUT job and resume it.

        Returns the updated job, or None if the job isn't in
        WAITING_FOR_INPUT state.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != JobStatus.WAITING_FOR_INPUT:
                return None
            merged = dict(job.human_answers)
            merged.update(answers)
            job.human_answers = merged
            job.pending_questions = tuple(
                q for q in job.pending_questions if q.get("id") not in answers
            )
            # If all questions answered, return to RUNNING so the runner resumes.
            if not job.pending_questions:
                job.status = JobStatus.RUNNING
            return job

    def is_cancelled(self, job_id: str) -> bool:
        """Return True if the job has been cancelled (status=ABORTED)."""
        return self.is_terminal(job_id) and (
            self.get(job_id) is not None
            and self.get(job_id).status == JobStatus.ABORTED
        )

    def cancel_event(self, job_id: str) -> threading.Event:
        """Return a threading.Event that fires when the job is cancelled.

        Background tasks call `event.wait(timeout)` between orchestrator
        steps to support prompt mid-run cancellation.
        """
        with self._lock:
            event = self._cancel_events.get(job_id)
            if event is None:
                event = threading.Event()
                # If the job is already cancelled when the event is created,
                # mark it set so `.wait()` returns immediately.
                job = self._jobs.get(job_id)
                if job is not None and job.status == JobStatus.ABORTED:
                    event.set()
                self._cancel_events[job_id] = event
            return event

    def _gc_cancel_event(self, job_id: str) -> None:
        with self._lock:
            self._cancel_events.pop(job_id, None)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._jobs.keys())

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._by_request.clear()
            self._cancel_events.clear()


class SqliteJobStore:
    """Persistent `JobStore` backed by SQLite (stdlib `sqlite3`).

    Schema:
        jobs(
            job_id TEXT PRIMARY KEY,
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,   -- JSON
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            termination_reason TEXT,
            result TEXT,                     -- JSON
            error TEXT
        )

    Suitable for single-process FastAPI deployments. For multi-worker
    production setups, swap to Postgres + a row-level lock.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        request_id TEXT UNIQUE NOT NULL,
        request_payload TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        termination_reason TEXT,
        result TEXT,
        error TEXT,
        pending_questions TEXT,
        human_answers TEXT,
        last_thinking TEXT,
        decision_log TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
            # Idempotent migrations for existing DBs (Sprint 10 + 11).
            for col in (
                "pending_questions", "human_answers", "last_thinking", "decision_log",
            ):
                try:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # column already exists
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, request_payload: dict[str, Any]) -> GenerationJob:
        request_id = compute_request_id(request_payload)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE request_id = ?", (request_id,),
            ).fetchone()
            if row is not None:
                return _row_to_job(row)

            job = GenerationJob(
                job_id=str(uuid.uuid4()),
                request_id=request_id,
                request_payload=request_payload,
            )
            conn.execute(
                """INSERT INTO jobs (job_id, request_id, request_payload, status,
                                    created_at, started_at, completed_at,
                                    termination_reason, result, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.job_id, job.request_id,
                    json.dumps(job.request_payload, default=str),
                    job.status.value, job.created_at,
                    job.started_at, job.completed_at,
                    job.termination_reason,
                    json.dumps(job.result, default=str) if job.result else None,
                    job.error,
                ),
            )
            conn.commit()
            return job

    def get(self, job_id: str) -> GenerationJob | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,),
            ).fetchone()
            return _row_to_job(row) if row else None

    def update(self, job_id: str, **fields: Any) -> GenerationJob:
        valid_fields = {
            "status", "started_at", "completed_at", "termination_reason",
            "result", "error", "pending_questions", "human_answers",
            "last_thinking", "decision_log",
        }
        sets = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in valid_fields:
                raise AttributeError(f"GenerationJob has no field {key!r}")
            if key == "status":
                value = value.value if isinstance(value, JobStatus) else value
            if key == "result" and value is not None and not isinstance(value, (str, bytes)):
                value = json.dumps(value, default=str)
            if key == "pending_questions":
                value = json.dumps(list(value), default=str)
            if key == "human_answers":
                value = json.dumps(dict(value), default=str)
            if key == "decision_log":
                value = json.dumps(list(value), default=str)
            sets.append(f"{key} = ?")
            values.append(value)
        if not sets:
            raise ValueError("update() requires at least one field")
        values.append(job_id)

        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?", values,
            )
            if cur.rowcount == 0:
                raise KeyError(f"job {job_id} not found")
            conn.commit()
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,),
            ).fetchone()
            assert row is not None
            return _row_to_job(row)

    def list_ids(self) -> list[str]:
        with self._lock, self._connect() as conn:
            return [r[0] for r in conn.execute("SELECT job_id FROM jobs").fetchall()]

    def clear(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM jobs")
            conn.commit()

    def is_cancelled(self, job_id: str) -> bool:
        job = self.get(job_id)
        return job is not None and job.status == JobStatus.ABORTED

    def submit_answer(
        self, job_id: str, answers: dict[str, str]
    ) -> GenerationJob | None:
        job = self.get(job_id)
        if job is None or job.status != JobStatus.WAITING_FOR_INPUT:
            return None
        merged = dict(job.human_answers)
        merged.update(answers)
        new_pending = tuple(
            q for q in job.pending_questions if q.get("id") not in answers
        )
        new_status = JobStatus.RUNNING if not new_pending else JobStatus.WAITING_FOR_INPUT
        return self.update(
            job_id,
            human_answers=merged,
            pending_questions=new_pending,
            status=new_status,
        )

    def cancel_event(self, job_id: str) -> threading.Event:
        """Polling-based event for SQLite (cross-process not supported).

        For in-memory store, this is a real Event; for SQLite (which may be
        shared across processes), we approximate by checking is_cancelled().
        """
        event = threading.Event()
        if self.is_cancelled(job_id):
            event.set()
        return event

    def record_decision(
        self, job_id: str, decision: dict[str, Any]
    ) -> GenerationJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        log = list(job.decision_log) + [decision]
        new_thinking = decision.get("think") or job.last_thinking
        return self.update(
            job_id,
            decision_log=tuple(log),
            last_thinking=new_thinking,
        )


def _row_to_job(row: sqlite3.Row) -> GenerationJob:
    payload = json.loads(row["request_payload"]) if row["request_payload"] else {}
    result = json.loads(row["result"]) if row["result"] else None
    pending = tuple(json.loads(row["pending_questions"])) if row["pending_questions"] else ()
    answers = json.loads(row["human_answers"]) if row["human_answers"] else {}
    decision_log = tuple(json.loads(row["decision_log"])) if row["decision_log"] else ()
    return GenerationJob(
        job_id=row["job_id"],
        request_id=row["request_id"],
        request_payload=payload,
        status=JobStatus(row["status"]),
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        termination_reason=row["termination_reason"],
        result=result,
        error=row["error"],
        pending_questions=pending,
        human_answers=answers,
        last_thinking=row["last_thinking"] or "",
        decision_log=decision_log,
    )


def _default_store() -> JobStoreProtocol:
    """Pick the default store based on environment.

    Production: SQLite (jobs survive process restart).
    Tests/development: in-memory (clean slate per process).

    Override via env `COGENAI_JOB_STORE` (memory | sqlite:/path/to/db).
    """
    import os
    override = os.environ.get("COGENAI_JOB_STORE", "").strip()
    if override == "":
        # Default: in-memory. Tests set their own; production can set the env var.
        return JobStore()
    if override.startswith("sqlite:"):
        return SqliteJobStore(override[len("sqlite:"):])
    if override == "memory":
        return JobStore()
    raise ValueError(
        f"unknown COGENAI_JOB_STORE={override!r}; expected 'memory' or 'sqlite:<path>'"
    )


# Module-level singleton (FastAPI dependency-friendly). Backed by in-memory
# by default; can be swapped via `set_job_store()` for SQLite or tests.
_store: JobStoreProtocol = _default_store()


def get_job_store() -> JobStoreProtocol:
    """Return the process-wide JobStore instance."""
    return _store


def set_job_store(store: JobStoreProtocol) -> None:
    """Replace the process-wide JobStore (used by tests and app bootstrap)."""
    global _store
    _store = store


def reset_to_default_store() -> None:
    """Rebuild the default store from environment (used by tests)."""
    global _store
    _store = _default_store()


# ----------------------------- Event bus -----------------------------

class JobEventBus:
    """In-process pub/sub of job state transitions.

    Subscribers register a callback and receive a copy of the GenerationJob
    after every status change. Used by the WebSocket endpoint to push
    real-time updates to clients without polling.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, list] = {}

    def subscribe(self, job_id: str, callback) -> None:
        with self._lock:
            self._subscribers.setdefault(job_id, []).append(callback)

    def unsubscribe(self, job_id: str, callback) -> None:
        with self._lock:
            callbacks = self._subscribers.get(job_id, [])
            if callback in callbacks:
                callbacks.remove(callback)
            if not callbacks:
                self._subscribers.pop(job_id, None)

    def publish(self, job: GenerationJob) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(job.job_id, ()))
        for cb in callbacks:
            with contextlib.suppress(Exception):
                cb(job)


_event_bus = JobEventBus()


def get_event_bus() -> JobEventBus:
    return _event_bus


def make_job_store(backend: str = "memory", db_path: str | None = None) -> JobStoreProtocol:
    """Factory: 'memory' or 'sqlite' (requires `db_path`)."""
    if backend == "memory":
        return JobStore()
    if backend == "sqlite":
        if not db_path:
            raise ValueError("db_path is required for sqlite backend")
        return SqliteJobStore(db_path)
    raise ValueError(f"unknown backend: {backend}")
