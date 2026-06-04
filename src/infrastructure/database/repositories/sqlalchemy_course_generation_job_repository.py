"""SQLAlchemy adapter for `CourseGenerationJobRepository`."""
from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.generation.entities.course_generation_job import CourseGenerationJob
from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.repositories.course_generation_job_repository import (
    CourseGenerationJobRepository,
)
from src.domain.generation.value_objects.job_status import JobStatus
from src.domain.generation.value_objects.source_type import SourceType
from src.infrastructure.database.models.course_generation_job_model import (
    CourseGenerationJobModel,
)


class SqlAlchemyCourseGenerationJobRepository(CourseGenerationJobRepository):
    """Persist `CourseGenerationJob` to a relational database.

    The job's `sources` are serialized to JSON (TEXT column) to
    keep the schema simple. The MVP does not query inside sources,
    so JSON storage is fine.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(self, job: CourseGenerationJob) -> None:
        async with self._session_factory() as session:
            model = await session.get(CourseGenerationJobModel, job.id)
            if model is None:
                model = CourseGenerationJobModel(id=job.id)
                session.add(model)
            self._update_model(model, job)
            await session.commit()

    async def find_by_id(self, job_id: str) -> CourseGenerationJob | None:
        async with self._session_factory() as session:
            model = await session.get(CourseGenerationJobModel, job_id)
            if model is None:
                return None
            return self._to_domain(model)

    async def list_by_course(
        self,
        course_id: str,
    ) -> list[CourseGenerationJob]:
        async with self._session_factory() as session:
            stmt = (
                select(CourseGenerationJobModel)
                .where(CourseGenerationJobModel.course_id == course_id)
                .order_by(CourseGenerationJobModel.created_at.desc())
            )
            result = await session.execute(stmt)
            models: Sequence[CourseGenerationJobModel] = result.scalars().all()
            return [self._to_domain(m) for m in models]

    @staticmethod
    def _update_model(
        model: CourseGenerationJobModel,
        job: CourseGenerationJob,
    ) -> None:
        model.course_id = job.course_id
        model.status = job.status.value
        model.sources_json = json.dumps(
            [
                {
                    "source_type": s.source_type.value,
                    "content": s.content,
                    "url": s.url,
                    "title": s.title,
                    "extracted_text": s.extracted_text,
                }
                for s in job.sources
            ]
        )
        model.error_message = job.error_message
        model.concepts_extracted = job.concepts_extracted
        model.relations_extracted = job.relations_extracted
        model.started_at = job.started_at
        model.completed_at = job.completed_at
        model.created_at = job.created_at

    @staticmethod
    def _to_domain(model: CourseGenerationJobModel) -> CourseGenerationJob:
        sources: list[CourseSource] = []
        for raw in json.loads(model.sources_json or "[]"):
            source = CourseSource(
                source_type=SourceType(raw["source_type"]),
                content=raw.get("content"),
                url=raw.get("url"),
                title=raw.get("title"),
            )
            if raw.get("extracted_text"):
                source.set_extracted_text(raw["extracted_text"])
            sources.append(source)
        return CourseGenerationJob(
            id=model.id,
            course_id=model.course_id,
            sources=sources,
            status=JobStatus(model.status),
            created_at=model.created_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            concepts_extracted=model.concepts_extracted,
            relations_extracted=model.relations_extracted,
            error_message=model.error_message,
        )
