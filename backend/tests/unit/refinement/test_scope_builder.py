from __future__ import annotations

import pytest

from cogenai.application.orchestrator.context_synthesizer import GenerationContext
from cogenai.application.orchestrator.curriculum_planner import (
    CourseSkeleton,
    ModuleSpec,
    Prerequisite,
    SectionSpec,
)
from cogenai.application.orchestrator.refiners.base import TokenCapExceeded
from cogenai.application.orchestrator.refiners.scope_builder import ScopeBuilder
from cogenai.domain.course import ContentBlock, Course, Module, Section
from cogenai.domain.shared.value_objects import (
    new_block_id,
    new_course_id,
    new_module_id,
    new_section_id,
)

from ._fixtures import make_issue


def make_block(content=None, order=0, block_type="concept"):
    return ContentBlock(
        id=new_block_id(),
        type=block_type,
        order=order,
        content=content or {"markdown": "x"},
    )


def make_section(blocks=()):
    return Section(
        id=new_section_id(),
        title="Section 1",
        order=0,
        blocks=tuple(blocks),
        learning_objectives=["LO1"],
    )


def make_module(sections=()):
    return Module(
        id=new_module_id(),
        title="Module 1",
        summary="summary",
        order=0,
        sections=tuple(sections),
    )


def make_course(modules=()):
    return Course(
        id=new_course_id(),
        title="Course",
        summary="summary",
        learning_outcomes=("Outcome 1",),
        modules=tuple(modules),
    )


def make_plan(modules=(), sections=()):
    return CourseSkeleton(
        topic="Python",
        modules=tuple(modules),
        sections=tuple(sections),
        prerequisites=(),
    )


def make_context():
    return GenerationContext(
        topic="Python",
        audience="beginner",
        difficulty="beginner",
        learning_outcomes=("Variables",),
        text_instructions="",
    )


class TestScopeBuilder:

    def setup_method(self):
        self.builder = ScopeBuilder()

    def test_block_level_payload_under_cap(self):
        block = make_block(content={"markdown": "x", "key_takeaways": ["a", "b"]})
        bundle = self.builder.build(
            level="block",
            target_id=str(block.id),
            target_object=block,
            issues=(make_issue(issue_id="i-1", scope="block", target_id=str(block.id)),),
        )
        assert bundle.estimated_tokens <= 1000
        assert bundle.scope.level == "block"
        assert bundle.scope.target_id == str(block.id)

    def test_section_level_payload_under_cap(self):
        section = make_section(blocks=[make_block(order=0), make_block(order=1)])
        bundle = self.builder.build(
            level="section",
            target_id=str(section.id),
            target_object=section,
            issues=(make_issue(issue_id="i-1", scope="section", target_id=str(section.id)),),
            siblings=("Section A", "Section B"),
        )
        assert bundle.estimated_tokens <= 1500

    def test_module_level_payload_under_cap(self):
        module = make_module(sections=[make_section(), make_section()])
        bundle = self.builder.build(
            level="module",
            target_id=str(module.id),
            target_object=module,
            issues=(make_issue(issue_id="i-1", scope="module", target_id=str(module.id)),),
            siblings=("Module 1", "Module 2"),
        )
        assert bundle.estimated_tokens <= 2000

    def test_plan_level_payload_under_cap(self):
        plan = make_plan(
            modules=[ModuleSpec(title=f"M{i}", summary="", order=i) for i in range(5)],
            sections=[SectionSpec(title=f"S{i}", topic="t", order=i) for i in range(10)],
        )
        bundle = self.builder.build(
            level="plan",
            target_id="course-1",
            target_object=plan,
            issues=(make_issue(issue_id="i-1", scope="course", target_id="course-1", category="structural"),),
        )
        assert bundle.estimated_tokens <= 1500

    def test_prerequisites_level_payload_under_cap(self):
        prereqs = tuple(
            Prerequisite(from_topic=f"t{i}", to_topic=f"t{i+1}") for i in range(5)
        )
        bundle = self.builder.build(
            level="prerequisites",
            target_id="course-1",
            target_object=prereqs,
            issues=(make_issue(issue_id="i-1", scope="course", target_id="course-1", category="prerequisite"),),
            siblings=("Python",),
        )
        assert bundle.estimated_tokens <= 600

    def test_context_level_payload_under_cap(self):
        ctx = make_context()
        bundle = self.builder.build(
            level="context",
            target_id="course-1",
            target_object=ctx,
            issues=(make_issue(issue_id="i-1", scope="course", target_id="course-1", category="audience_alignment"),),
        )
        assert bundle.estimated_tokens <= 800

    def test_token_cap_exceeded_raises(self):
        huge_block = make_block(
            content={"markdown": "x" * 20000, "key_takeaways": ["y" * 1000] * 100}
        )
        issue = make_issue(
            issue_id="i-1",
            scope="block",
            target_id=str(huge_block.id),
            message="x" * 20000,
        )
        with pytest.raises(TokenCapExceeded) as excinfo:
            self.builder.build(
                level="block",
                target_id=str(huge_block.id),
                target_object=huge_block,
                issues=(issue,),
            )
        assert excinfo.value.level == "block"
        assert excinfo.value.estimated_tokens > excinfo.value.cap

    def test_scope_carries_issue_ids(self):
        block = make_block()
        issue = make_issue(issue_id="i-99", scope="block", target_id=str(block.id))
        bundle = self.builder.build(
            level="block",
            target_id=str(block.id),
            target_object=block,
            issues=(issue,),
        )
        assert "i-99" in bundle.scope.issue_ids

    def test_siblings_included_in_sibling_summaries(self):
        block = make_block()
        bundle = self.builder.build(
            level="block",
            target_id=str(block.id),
            target_object=block,
            issues=(make_issue(issue_id="i-1", scope="block", target_id=str(block.id)),),
            siblings=("Section 1", "Section 2", "Section 3"),
        )
        assert len(bundle.scope.sibling_summaries) == 3

    def test_estimate_tokens_is_deterministic(self):
        block = make_block()
        bundle1 = self.builder.build(
            level="block",
            target_id=str(block.id),
            target_object=block,
            issues=(make_issue(issue_id="i-1", scope="block", target_id=str(block.id)),),
        )
        bundle2 = self.builder.build(
            level="block",
            target_id=str(block.id),
            target_object=block,
            issues=(make_issue(issue_id="i-1", scope="block", target_id=str(block.id)),),
        )
        assert bundle1.estimated_tokens == bundle2.estimated_tokens
