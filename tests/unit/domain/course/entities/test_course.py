import pytest

from src.domain.course.entities.course import Course
from src.domain.course.entities.module import Module
from src.domain.shared.exceptions.validation_error import ValidationError


class TestCourseInstantiation:
    def test_creates_course_with_minimal_data(self, sample_course_title):
        course = Course(title=sample_course_title)

        assert course.id is not None
        assert course.title == sample_course_title
        assert course.description is None
        assert course.modules == []

    def test_creates_course_with_description(self, sample_course_title):
        course = Course(
            title=sample_course_title,
            description="A complete course on ML",
        )

        assert course.description == "A complete course on ML"

    def test_strips_whitespace_from_title(self):
        course = Course(title="  Padded Title  ")

        assert course.title == "Padded Title"

    def test_strips_whitespace_from_description(self):
        course = Course(
            title="Title",
            description="  description with spaces  ",
        )

        assert course.description == "description with spaces"

    def test_treats_empty_description_as_none(self):
        course = Course(title="Title", description="")

        assert course.description is None

    def test_treats_whitespace_only_description_as_empty_string(self):
        course = Course(title="Title", description="   ")

        assert course.description == ""

    def test_generates_uuid_id_when_not_provided(self):
        course = Course(title="Title")

        assert isinstance(course.id, str)
        assert len(course.id) == 36
        assert course.id.count("-") == 4

    def test_preserves_provided_id(self):
        course = Course(title="Title", id="custom-id-123")

        assert course.id == "custom-id-123"

    def test_generates_unique_ids(self):
        course_a = Course(title="A")
        course_b = Course(title="B")

        assert course_a.id != course_b.id


class TestCourseValidation:
    def test_raises_validation_error_on_empty_title(self):
        with pytest.raises(ValidationError, match="title cannot be empty"):
            Course(title="")

    def test_raises_validation_error_on_whitespace_title(self):
        with pytest.raises(ValidationError, match="title cannot be empty"):
            Course(title="   \t\n  ")


class TestCourseModuleManagement:
    def test_add_module_appends_to_list(self):
        course = Course(title="Title")
        module = Module(title="M1", order=0)

        course.add_module(module)

        assert len(course.modules) == 1
        assert course.modules[0] is module

    def test_add_module_keeps_modules_sorted_by_order(self):
        course = Course(title="Title")
        m1 = Module(title="M1", order=2)
        m2 = Module(title="M2", order=0)
        m3 = Module(title="M3", order=1)

        course.add_module(m1)
        course.add_module(m2)
        course.add_module(m3)

        assert [m.order for m in course.modules] == [0, 1, 2]

    def test_remove_module_filters_by_id(self):
        course = Course(title="Title")
        m1 = Module(title="M1", order=0)
        m2 = Module(title="M2", order=1)
        course.add_module(m1)
        course.add_module(m2)

        course.remove_module(m1.id)

        assert course.modules == [m2]

    def test_remove_nonexistent_module_leaves_list_unchanged(self):
        course = Course(title="Title")
        m1 = Module(title="M1", order=0)
        course.add_module(m1)

        course.remove_module("does-not-exist")

        assert course.modules == [m1]

    def test_get_module_returns_matching_module(self):
        course = Course(title="Title")
        m1 = Module(title="M1", order=0)
        course.add_module(m1)

        assert course.get_module(m1.id) is m1

    def test_get_module_returns_none_when_not_found(self):
        course = Course(title="Title")

        assert course.get_module("missing") is None
