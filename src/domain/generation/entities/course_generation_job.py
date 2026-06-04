from datetime import datetime
from uuid import uuid4

from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.value_objects.job_status import JobStatus
from src.domain.shared.exceptions.validation_error import ValidationError


class CourseGenerationJob:
    """An aggregate that tracks the lifecycle of a generation run.

    The job is the unit of persistence for the generation
    pipeline. The application service (`CourseGenerationService`)
    creates one job per generation request, mutates it through the
    pipeline stages, and the repository persists it to Postgres so
    the user can monitor progress and resume after failures.

    State transitions are explicit and validated. The job cannot
    transition out of COMPLETED.
    """

    def __init__(
        self,
        course_id: str,
        sources: list[CourseSource],
        id: str | None = None,
        status: JobStatus = JobStatus.PENDING,
        created_at: datetime | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        concepts_extracted: int = 0,
        relations_extracted: int = 0,
        error_message: str | None = None,
    ):
        self.id = id or str(uuid4())
        self.course_id = course_id
        self.sources = list(sources)
        self.status = status
        self.created_at = created_at or datetime.utcnow()
        self.started_at = started_at
        self.completed_at = completed_at
        self.concepts_extracted = concepts_extracted
        self.relations_extracted = relations_extracted
        self.error_message = error_message
        self._validate()

    def _validate(self) -> None:
        if not self.course_id:
            raise ValidationError("CourseGenerationJob course_id cannot be empty.")
        if not self.sources:
            raise ValidationError(
                "CourseGenerationJob requires at least one source."
            )
        if not isinstance(self.status, JobStatus):
            raise ValidationError(
                f"status must be a JobStatus, got {type(self.status).__name__}."
            )
        if self.concepts_extracted < 0 or self.relations_extracted < 0:
            raise ValidationError(
                "concepts_extracted and relations_extracted cannot be negative."
            )

    def mark_running(self) -> None:
        if self.status is JobStatus.COMPLETED:
            raise ValidationError("Cannot transition out of COMPLETED.")
        if self.status is JobStatus.RUNNING:
            return
        if self.status not in (JobStatus.PENDING, JobStatus.FAILED):
            raise ValidationError(
                f"Cannot transition from {self.status.name} to RUNNING."
            )
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.error_message = None

    def mark_completed(
        self,
        concepts_extracted: int,
        relations_extracted: int,
    ) -> None:
        if self.status is not JobStatus.RUNNING:
            raise ValidationError(
                f"Cannot mark COMPLETED from {self.status.name}; "
                "job must be RUNNING."
            )
        if concepts_extracted < 0 or relations_extracted < 0:
            raise ValidationError(
                "concepts_extracted and relations_extracted cannot be negative."
            )
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.concepts_extracted = concepts_extracted
        self.relations_extracted = relations_extracted
        self.error_message = None

    def mark_failed(self, error_message: str) -> None:
        if self.status is JobStatus.COMPLETED:
            raise ValidationError("Cannot transition out of COMPLETED.")
        if not error_message or not error_message.strip():
            raise ValidationError("error_message cannot be empty when failing a job.")
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message.strip()

    def add_source(self, source: CourseSource) -> None:
        if self.status is not JobStatus.PENDING:
            raise ValidationError(
                f"Cannot add sources to a job in {self.status.name} state."
            )
        self.sources.append(source)

    @property
    def duration_seconds(self) -> float | None:
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def __repr__(self) -> str:
        return (
            f"CourseGenerationJob(id={self.id[:8]}, "
            f"course={self.course_id!r}, status={self.status.name}, "
            f"sources={len(self.sources)})"
        )
