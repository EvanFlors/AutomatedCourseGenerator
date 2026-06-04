import pytest
from datetime import datetime

from src.domain.generation.entities.course_generation_job import CourseGenerationJob
from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.value_objects.job_status import JobStatus
from src.domain.generation.value_objects.source_type import SourceType
from src.domain.shared.exceptions.validation_error import ValidationError


class TestJobCreation:
    def test_creates_pending_job(self):
        job = CourseGenerationJob(
            course_id="c-1",
            sources=[CourseSource(source_type=SourceType.TEXT, content="hi")],
        )

        assert job.status == JobStatus.PENDING
        assert job.concepts_extracted == 0
        assert job.relations_extracted == 0
        assert job.error_message is None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.created_at is not None

    def test_rejects_empty_course_id(self):
        with pytest.raises(ValidationError, match="course_id"):
            CourseGenerationJob(
                course_id="",
                sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
            )

    def test_rejects_no_sources(self):
        with pytest.raises(ValidationError, match="at least one source"):
            CourseGenerationJob(course_id="c", sources=[])

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError, match="status must be a JobStatus"):
            CourseGenerationJob(
                course_id="c",
                sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
                status="running",
            )

    def test_rejects_negative_counters(self):
        with pytest.raises(ValidationError, match="cannot be negative"):
            CourseGenerationJob(
                course_id="c",
                sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
                concepts_extracted=-1,
            )


class TestStatusTransitions:
    def test_mark_running_from_pending(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )

        job.mark_running()

        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.error_message is None

    def test_mark_running_from_failed_is_a_retry(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()
        job.mark_failed("boom")
        first_started = job.started_at

        job.mark_running()

        assert job.status == JobStatus.RUNNING
        assert job.error_message is None
        assert job.started_at != first_started

    def test_mark_running_is_idempotent(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()
        first_started = job.started_at

        job.mark_running()

        assert job.started_at == first_started

    def test_cannot_mark_running_from_completed(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()
        job.mark_completed(concepts_extracted=1, relations_extracted=0)

        with pytest.raises(ValidationError, match="Cannot transition out of COMPLETED"):
            job.mark_running()

    def test_cannot_mark_completed_from_pending(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )

        with pytest.raises(ValidationError, match="must be RUNNING"):
            job.mark_completed(concepts_extracted=1, relations_extracted=0)

    def test_cannot_mark_completed_with_negative_counters(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()

        with pytest.raises(ValidationError, match="cannot be negative"):
            job.mark_completed(concepts_extracted=-1, relations_extracted=0)

    def test_cannot_mark_failed_with_empty_message(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()

        with pytest.raises(ValidationError, match="error_message cannot be empty"):
            job.mark_failed("   ")

    def test_cannot_mark_failed_from_completed(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()
        job.mark_completed(1, 0)

        with pytest.raises(ValidationError, match="Cannot transition out of COMPLETED"):
            job.mark_failed("too late")


class TestSourceManagement:
    def test_add_source_in_pending(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="a")],
        )

        job.add_source(CourseSource(source_type=SourceType.TEXT, content="b"))

        assert len(job.sources) == 2

    def test_cannot_add_source_after_running(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="a")],
        )
        job.mark_running()

        with pytest.raises(ValidationError, match="Cannot add sources"):
            job.add_source(CourseSource(source_type=SourceType.TEXT, content="b"))


class TestDuration:
    def test_duration_none_until_completed(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )

        assert job.duration_seconds is None

    def test_duration_calculated_after_completion(self):
        job = CourseGenerationJob(
            course_id="c",
            sources=[CourseSource(source_type=SourceType.TEXT, content="x")],
        )
        job.mark_running()
        job.started_at = datetime(2026, 1, 1, 10, 0, 0)
        job.mark_completed(1, 0)
        job.completed_at = datetime(2026, 1, 1, 10, 0, 30)

        assert job.duration_seconds == 30.0
