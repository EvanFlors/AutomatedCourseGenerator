from __future__ import annotations

from cogenai.domain.course import ContentBlock, Course, Module, Section
from cogenai.domain.shared.value_objects import new_block_id, new_module_id, new_section_id
from cogenai.interfaces.dto.course import CourseDTO


class TestCourseDTOFromDomain:
    def test_minimal_course_maps_to_dto(self):
        course = Course(
            title="Python for beginners",
            summary="Intro",
            learning_outcomes=("Variables",),
            language="en",
            tags=("python", "basics"),
            estimated_duration_minutes=30,
        )
        dto = CourseDTO.from_domain(course)
        assert dto.title == "Python for beginners"
        assert dto.language == "en"
        assert dto.metadata.tags == ["python", "basics"]
        assert dto.metadata.estimated_duration_minutes == 30
        assert dto.audience is None
        assert dto.modules == []

    def test_full_hierarchy_round_trip(self):
        block = ContentBlock(
            id=new_block_id(), type="concept", order=0,
            content={"prompt": "x"}, estimated_time_minutes=5,
        )
        section = Section(
            id=new_section_id(), title="S", order=0,
            blocks=(block,), learning_objectives=["LO"],
        )
        module = Module(id=new_module_id(), title="M", order=0, sections=(section,))
        course = Course(
            title="C", summary="sum", learning_outcomes=("A",),
            modules=(module,), tags=("t1",), estimated_duration_minutes=5,
        )
        dto = CourseDTO.from_domain(course)
        assert len(dto.modules) == 1
        assert dto.modules[0].title == "M"
        assert dto.modules[0].sections[0].title == "S"
        assert dto.modules[0].sections[0].blocks[0].metadata["estimated_time_minutes"] == 5