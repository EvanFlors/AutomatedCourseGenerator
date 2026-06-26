from __future__ import annotations

import pytest

from cogenai.application.orchestrator.refiners.dependency_graph import DependencyGraph
from cogenai.domain.course import ContentBlock, Course, Module, Section
from cogenai.domain.shared.value_objects import (
    new_block_id,
    new_course_id,
    new_module_id,
    new_section_id,
)


def make_block():
    return ContentBlock(
        id=new_block_id(),
        type="concept",
        order=0,
        content={"markdown": "x"},
    )


def make_section(blocks=()):
    return Section(
        id=new_section_id(),
        title="Section",
        order=0,
        blocks=tuple(blocks),
        learning_objectives=["LO1"],
    )


def make_module(sections=()):
    return Module(
        id=new_module_id(),
        title="Module",
        summary="",
        order=0,
        sections=tuple(sections),
    )


def make_course(modules=()):
    return Course(
        id=new_course_id(),
        title="Course",
        summary="",
        learning_outcomes=("Outcome 1",),
        modules=tuple(modules),
    )


class TestDependencyGraph:

    def test_from_course_builds_id_maps(self):
        course = make_course(
            modules=[
                make_module(
                    sections=[
                        make_section(blocks=[make_block(), make_block()]),
                    ]
                ),
            ]
        )
        graph = DependencyGraph.from_course(course)
        assert str(course.id) in graph.course_to_modules
        assert len(graph.course_to_modules[str(course.id)]) == 1
        module = course.modules[0]
        assert len(graph.module_to_sections[str(module.id)]) == 1
        section = module.sections[0]
        assert len(graph.section_to_blocks[str(section.id)]) == 2

    def test_from_course_empty(self):
        course = make_course(modules=[])
        graph = DependencyGraph.from_course(course)
        assert graph.course_to_modules[str(course.id)] == ()

    def test_update_module_sections(self):
        course = make_course(modules=[make_module()])
        graph = DependencyGraph.from_course(course)
        module_id = course.modules[0].id
        graph.update_module(module_id, ("s1", "s2", "s3"))
        assert graph.module_to_sections[str(module_id)] == ("s1", "s2", "s3")

    def test_update_section_blocks(self):
        course = make_course(modules=[make_module(sections=[make_section(blocks=[make_block()])])])
        graph = DependencyGraph.from_course(course)
        section = course.modules[0].sections[0]
        graph.update_section(section.id, ("b1", "b2"))
        assert graph.section_to_blocks[str(section.id)] == ("b1", "b2")

    def test_invalidate_leaves_returns_block_ids(self):
        course = make_course(
            modules=[
                make_module(
                    sections=[
                        make_section(blocks=[make_block(), make_block()]),
                        make_section(blocks=[make_block()]),
                    ]
                ),
            ]
        )
        graph = DependencyGraph.from_course(course)
        module_id = course.modules[0].id
        invalidated = graph.invalidate_leaves(module_id)
        assert len(invalidated) == 3

    def test_invalidate_leaves_unknown_module(self):
        course = make_course(modules=[])
        graph = DependencyGraph.from_course(course)
        assert graph.invalidate_leaves(new_module_id()) == ()

    def test_cascade_invalidates_returns_all_blocks(self):
        course = make_course(
            modules=[
                make_module(sections=[make_section(blocks=[make_block(), make_block()])]),
                make_module(sections=[make_section(blocks=[make_block()])]),
            ]
        )
        graph = DependencyGraph.from_course(course)
        all_blocks = graph.cascade_invalidates()
        assert len(all_blocks) == 3

    def test_d_r1_no_deletion_via_graph(self):
        course = make_course(
            modules=[
                make_module(sections=[make_section(blocks=[make_block()])]),
                make_module(sections=[make_section(blocks=[make_block()])]),
            ]
        )
        graph = DependencyGraph.from_course(course)
        original_module_ids = tuple(str(m.id) for m in course.modules)
        assert all(mid in graph.course_to_modules[str(course.id)] for mid in original_module_ids)
