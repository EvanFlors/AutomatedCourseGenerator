"""Integration tests for SqlAlchemyCourseGenerationJobRepository.

Verifies the round-trip: domain aggregate -> ORM model ->
domain aggregate. Uses the same in-memory SQLite engine as
the rest of the persistence tests.
"""
import pytest

from src.domain.generation.entities.course_generation_job import CourseGenerationJob
from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.value_objects.job_status import JobStatus
from src.domain.generation.value_objects.source_type import SourceType
from src.infrastructure.database.models import CourseGenerationJobModel
from src.infrastructure.database.repositories.sqlalchemy_course_generation_job_repository import (
    SqlAlchemyCourseGenerationJobRepository,
)

pytestmark = pytest.mark.asyncio


class TestSaveAndFind:
    async def test_save_new_job_then_find_by_id(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))
        job = CourseGenerationJob(
            course_id="course-1",
            sources=[CourseSource(source_type=SourceType.TEXT, content="hello world")],
        )

        await repo.save(job)
        loaded = await repo.find_by_id(job.id)

        assert loaded is not None
        assert loaded.id == job.id
        assert loaded.course_id == "course-1"
        assert loaded.status == JobStatus.PENDING
        assert len(loaded.sources) == 1
        assert loaded.sources[0].content == "hello world"

    async def test_save_updates_existing_job(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))
        job = CourseGenerationJob(
            course_id="course-1",
            sources=[CourseSource(source_type=SourceType.TEXT, content="hi")],
        )
        await repo.save(job)

        job.mark_running()
        await repo.save(job)

        loaded = await repo.find_by_id(job.id)
        assert loaded is not None
        assert loaded.status == JobStatus.RUNNING
        assert loaded.started_at is not None

    async def test_save_records_concepts_and_relations_counts(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))
        job = CourseGenerationJob(
            course_id="course-1",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()
        job.mark_completed(concepts_extracted=12, relations_extracted=5)

        await repo.save(job)
        loaded = await repo.find_by_id(job.id)

        assert loaded is not None
        assert loaded.status == JobStatus.COMPLETED
        assert loaded.concepts_extracted == 12
        assert loaded.relations_extracted == 5

    async def test_save_persists_error_message_on_failure(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))
        job = CourseGenerationJob(
            course_id="course-1",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()
        job.mark_failed("Gemini API timeout")

        await repo.save(job)
        loaded = await repo.find_by_id(job.id)

        assert loaded is not None
        assert loaded.status == JobStatus.FAILED
        assert loaded.error_message == "Gemini API timeout"
        assert loaded.completed_at is not None

    async def test_save_serializes_extracted_text_in_sources(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))
        source = CourseSource(source_type=SourceType.TEXT, content="raw")
        source.set_extracted_text("cleaned and trimmed")
        job = CourseGenerationJob(course_id="c", sources=[source])

        await repo.save(job)
        loaded = await repo.find_by_id(job.id)

        assert loaded is not None
        assert loaded.sources[0].extracted_text == "cleaned and trimmed"

    async def test_save_serializes_url_sources(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.URL, url="https://example.com")],
        )

        await repo.save(job)
        loaded = await repo.find_by_id(job.id)

        assert loaded is not None
        assert loaded.sources[0].source_type == SourceType.URL
        assert loaded.sources[0].url == "https://example.com"


class TestListByCourse:
    async def test_returns_empty_for_course_with_no_jobs(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))

        jobs = await repo.list_by_course("nope")

        assert jobs == []

    async def test_returns_jobs_newest_first(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))
        first = CourseGenerationJob(
            course_id="c-1",
            sources=[CourseSource(source_type=SourceType.TEXT, content="a")],
        )
        second = CourseGenerationJob(
            course_id="c-1",
            sources=[CourseSource(source_type=SourceType.TEXT, content="b")],
        )
        third = CourseGenerationJob(
            course_id="c-2",
            sources=[CourseSource(source_type=SourceType.TEXT, content="c")],
        )
        for job in (first, second, third):
            await repo.save(job)

        jobs = await repo.list_by_course("c-1")

        assert [j.id for j in jobs] == [second.id, first.id]

    async def test_filters_by_course_id(self, session):
        repo = SqlAlchemyCourseGenerationJobRepository(lambda: _factory(session))
        for course in ("a", "a", "b"):
            await repo.save(CourseGenerationJob(
                course_id=course,
                sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
            ))

        jobs_a = await repo.list_by_course("a")
        jobs_b = await repo.list_by_course("b")

        assert len(jobs_a) == 2
        assert len(jobs_b) == 1
        assert all(j.course_id == "a" for j in jobs_a)


class TestModelMapping:
    async def test_model_creation_persists_all_columns(self, session):
        from datetime import datetime

        from src.infrastructure.database.models import CourseGenerationJobModel

        model = CourseGenerationJobModel(
            id="job-1",
            course_id="c-1",
            status="running",
            sources_json='[{"source_type":"text","content":"x"}]',
            concepts_extracted=3,
            relations_extracted=2,
            created_at=datetime.utcnow(),
        )
        session.add(model)
        await session.commit()

        loaded = await session.get(CourseGenerationJobModel, "job-1")
        assert loaded is not None
        assert loaded.status == "running"
        assert loaded.concepts_extracted == 3
        assert loaded.relations_extracted == 2


def _factory(session):
    """Build a session factory that always returns the test session."""
    class _OneOff:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    return _OneOff()
