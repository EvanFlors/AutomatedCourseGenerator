from abc import ABC, abstractmethod

from src.domain.generation.entities.course_generation_job import CourseGenerationJob


class CourseGenerationJobRepository(ABC):
    """Persistence port for `CourseGenerationJob`.

    The repository is responsible for serializing the job to a
    relational store (Postgres in the MVP) and hydrating it back
    into a domain aggregate. It does not own the
    `CourseGenerationService` business logic.
    """

    @abstractmethod
    async def save(self, job: CourseGenerationJob) -> None:
        """Persist `job` (insert or update)."""

    @abstractmethod
    async def find_by_id(self, job_id: str) -> CourseGenerationJob | None:
        """Return the job with the given id, or None if not found."""

    @abstractmethod
    async def list_by_course(
        self,
        course_id: str,
    ) -> list[CourseGenerationJob]:
        """List all jobs associated with a course, newest first."""
