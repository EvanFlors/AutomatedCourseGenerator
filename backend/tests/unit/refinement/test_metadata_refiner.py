from __future__ import annotations

import json

import pytest

from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.evaluator import (
    EvaluationIssue,
)
from cogenai.agents_implementations.refiners import (
    IssueAnalysis,
    IssueAnalyzer,
    MetadataRefinerAgent,
    MetadataRefinerInput,
    MetadataRefinerOutput,
    _compute_duration_minutes,
)
from cogenai.agents_implementations.refiners.metadata_refiner import (
    MIN_TAGS, MAX_TAGS,
)
from cogenai.domain.course import ContentBlock, Course, Module, Section
from cogenai.domain.shared.value_objects import new_block_id, new_course_id, new_module_id
from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage

from ._fixtures import (
    FakeProvider,
    make_issue,
    make_metadata_response,
)


def _config() -> AgentConfig:
    return AgentConfig.default(model_name="stub-model")


def _course_with_modules(modules=()) -> Course:
    return Course(
        title="Python for beginners",
        summary="An intro course.",
        learning_outcomes=("Variables",),
        modules=tuple(modules),
    )


def _block(minutes: int = 5) -> ContentBlock:
    return ContentBlock(
        id=new_block_id(),
        type="concept",
        order=0,
        estimated_time_minutes=minutes,
    )


def _section_with_blocks(blocks=()) -> Section:
    return Section(
        id=__import__("cogenai.domain.shared.value_objects", fromlist=["new_section_id"]).new_section_id(),
        title="S",
        order=0,
        blocks=tuple(blocks),
        learning_objectives=["LO1"],
    )


def _module_with_section(section: Section) -> Module:
    return Module(
        id=new_module_id(),
        title="M",
        order=0,
        sections=(section,),
    )


class TestMetadataRefinerAgent:
    def test_run_returns_tags_and_language(self):
        provider = FakeProvider(returns=make_metadata_response(
            tags=["python", "basics", "syntax"], language="en",
        ))
        agent = MetadataRefinerAgent(_config(), provider)
        out = agent.run(MetadataRefinerInput(
            course_id=new_course_id(),
            current_tags=("old",),
            current_language="en",
            current_duration_minutes=0,
            topic="Python",
        ))
        assert isinstance(out, MetadataRefinerOutput)
        assert out.tags == ("python", "basics", "syntax")
        assert out.language == "en"

    def test_run_normalizes_tags(self):
        provider = FakeProvider(returns=make_metadata_response(
            tags=["  Python Basics  ", "CODE", "#fun", "code"],
        ))
        agent = MetadataRefinerAgent(_config(), provider)
        out = agent.run(MetadataRefinerInput(
            course_id=new_course_id(),
            current_tags=(),
            current_language="en",
            current_duration_minutes=0,
        ))
        assert "python-basics" in out.tags
        assert "code" in out.tags
        assert "fun" in out.tags
        assert out.tags.count("code") == 1

    def test_run_caps_to_max_tags(self):
        provider = FakeProvider(returns=make_metadata_response(
            tags=["t1", "t2", "t3", "t4", "t5", "t6", "t7"],
        ))
        agent = MetadataRefinerAgent(_config(), provider)
        out = agent.run(MetadataRefinerInput(
            course_id=new_course_id(),
            current_tags=(),
            current_language="en",
            current_duration_minutes=0,
        ))
        assert len(out.tags) == MAX_TAGS

    def test_run_pads_short_tags_from_current(self):
        provider = FakeProvider(returns=make_metadata_response(tags=["only-one"]))
        agent = MetadataRefinerAgent(_config(), provider)
        out = agent.run(MetadataRefinerInput(
            course_id=new_course_id(),
            current_tags=("python", "basics", "tutorial"),
            current_language="en",
            current_duration_minutes=0,
        ))
        assert len(out.tags) >= MIN_TAGS
        assert "only-one" in out.tags
        # The padding pulls from current_tags to reach MIN_TAGS
        assert "python" in out.tags or "basics" in out.tags

    def test_run_rejects_invalid_language(self):
        provider = FakeProvider(returns=make_metadata_response(language="klingon"))
        agent = MetadataRefinerAgent(_config(), provider)
        out = agent.run(MetadataRefinerInput(
            course_id=new_course_id(),
            current_tags=("x",),
            current_language="en",
            current_duration_minutes=0,
        ))
        assert out.language == "en"

    def test_run_preserves_duration_from_input(self):
        provider = FakeProvider(returns=make_metadata_response())
        agent = MetadataRefinerAgent(_config(), provider)
        out = agent.run(MetadataRefinerInput(
            course_id=new_course_id(),
            current_tags=("x",),
            current_language="en",
            current_duration_minutes=42,
        ))
        assert out.estimated_duration_minutes == 42

    def test_run_issues_addressed_propagated(self):
        provider = FakeProvider(returns=make_metadata_response(issues=("i-1", "i-2")))
        agent = MetadataRefinerAgent(_config(), provider)
        out = agent.run(MetadataRefinerInput(
            course_id=new_course_id(),
            current_tags=(),
            current_language="en",
            current_duration_minutes=0,
            issues=(make_issue(issue_id="i-1"), make_issue(issue_id="i-2")),
        ))
        assert out.issues_addressed == ("i-1", "i-2")

    def test_yaml_prompt_is_used(self):
        from cogenai.prompt import get_prompt as yaml_get_prompt
        bundle = yaml_get_prompt("metadata_refiner", "1.0.0")
        assert bundle is not None
        assert "OUTPUT RULES" in bundle.system_prompt
        assert "tags" in bundle.system_prompt
        assert "language" in bundle.system_prompt


class TestComputeDurationMinutes:
    def test_zero_for_empty_course(self):
        c = _course_with_modules()
        assert _compute_duration_minutes(c) == 0

    def test_sums_block_minutes(self):
        s = _section_with_blocks([_block(5), _block(10)])
        m = _module_with_section(s)
        c = _course_with_modules([m])
        assert _compute_duration_minutes(c) == 15

    def test_sums_across_modules(self):
        s1 = _section_with_blocks([_block(5)])
        s2 = _section_with_blocks([_block(7), _block(3)])
        m1 = _module_with_section(s1)
        m2 = Module(id=new_module_id(), title="M2", order=1, sections=(s2,))
        c = _course_with_modules([m1, m2])
        assert _compute_duration_minutes(c) == 15

    def test_accepts_course_bundle(self):
        from dataclasses import dataclass
        @dataclass
        class FakeBundle:
            course: Course
        s = _section_with_blocks([_block(8)])
        m = _module_with_section(s)
        c = _course_with_modules([m])
        bundle = FakeBundle(course=c)
        assert _compute_duration_minutes(bundle) == 8


class TestIssueAnalyzerRoutesMetadata:
    def test_metadata_category_routes_to_metadata_level(self):
        analyzer = IssueAnalyzer()
        issues = (
            make_issue(issue_id="i-1", scope="course", category="metadata"),
        )
        analysis = analyzer.analyze(issues)
        assert "i-1" in [i.id for i in analysis.issues_for("metadata")]

    def test_metadata_in_analyzer_dict(self):
        analyzer = IssueAnalyzer()
        issues = (make_issue(scope="course", category="metadata"),)
        analysis = analyzer.analyze(issues)
        assert "metadata" in analysis.by_level
        assert len(analysis.by_level["metadata"]) == 1

    def test_context_routes_still_work(self):
        analyzer = IssueAnalyzer()
        issues = (make_issue(scope="course", category="audience_alignment"),)
        analysis = analyzer.analyze(issues)
        assert len(analysis.by_level["context"]) == 1
        assert len(analysis.by_level["metadata"]) == 0

    def test_metadata_cascade_is_empty(self):
        analyzer = IssueAnalyzer()
        issues = (make_issue(scope="course", category="metadata"),)
        analysis = analyzer.analyze(issues)
        assert analysis.cascade.get("metadata", ()) == ()

    def test_context_cascade_includes_metadata(self):
        analyzer = IssueAnalyzer()
        issues = (make_issue(scope="course", category="audience_alignment"),)
        analysis = analyzer.analyze(issues)
        assert "metadata" in analysis.cascade.get("context", ())
