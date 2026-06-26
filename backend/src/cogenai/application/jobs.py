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


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    ABORTED = "aborted"


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


class JobStore:
    """Thread-safe in-memory store keyed by job_id, with idempotency by request_id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, GenerationJob] = {}
        self._by_request: dict[str, str] = {}

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

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._jobs.keys())

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._by_request.clear()


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
        error TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
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
            "result", "error",
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


def _row_to_job(row: sqlite3.Row) -> GenerationJob:
    payload = json.loads(row["request_payload"]) if row["request_payload"] else {}
    result = json.loads(row["result"]) if row["result"] else None
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
    )


# Module-level singleton (FastAPI dependency-friendly). Backed by in-memory
# by default; can be swapped via `set_job_store()` for SQLite or tests.
_store: JobStoreProtocol = JobStore()


def get_job_store() -> JobStoreProtocol:
    """Return the process-wide JobStore instance."""
    return _store


def set_job_store(store: JobStoreProtocol) -> None:
    """Replace the process-wide JobStore (used by tests and app bootstrap)."""
    global _store
    _store = store


def make_job_store(backend: str = "memory", db_path: str | None = None) -> JobStoreProtocol:
    """Factory: 'memory' or 'sqlite' (requires `db_path`)."""
    if backend == "memory":
        return JobStore()
    if backend == "sqlite":
        if not db_path:
            raise ValueError("db_path is required for sqlite backend")
        return SqliteJobStore(db_path)
    raise ValueError(f"unknown backend: {backend}")
