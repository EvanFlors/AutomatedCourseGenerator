from __future__ import annotations

import pytest

from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.context_synthesizer import GenerationContext
from cogenai.application.orchestrator.curriculum_planner import (
    CourseSkeleton,
    ModuleSpec,
    Prerequisite,
    SectionSpec,
)
from cogenai.application.orchestrator.refiners.block_refiner import BlockRefinerAgent
from cogenai.application.orchestrator.refiners.context_refiner import ContextRefinerAgent
from cogenai.application.orchestrator.refiners.exceptions import (
    RefinerOutputTruncated,
    RefinerSchemaMismatch,
)
from cogenai.application.orchestrator.refiners.module_refiner import ModuleRefinerAgent
from cogenai.application.orchestrator.refiners.plan_refiner import (
    PlanRefinerAgent,
    merge_plan,
)
from cogenai.application.orchestrator.refiners.prerequisites_refiner import (
    PrerequisitesRefinerAgent,
)
from cogenai.application.orchestrator.refiners.section_refiner import SectionRefinerAgent
from cogenai.domain.course import ContentBlock, Module, Section
from cogenai.domain.shared.value_objects import (
    new_block_id,
    new_course_id,
    new_module_id,
    new_section_id,
)

from ._fixtures import (
    FakeProvider,
    StubProvider,
    _config,
    make_block_response,
    make_context_response,
    make_issue,
    make_module_response,
    make_plan_response,
    make_prereqs_response,
    make_section_response,
)


def _block():
    return ContentBlock(
        id=new_block_id(),
        type="exercise",
        order=0,
        content={"prompt": "old prompt", "hints": ["a"]},
    )


def _section():
    return Section(
        id=new_section_id(),
        title="Section",
        order=0,
        blocks=(_block(),),
        learning_objectives=["LO1"],
    )


def _module():
    return Module(
        id=new_module_id(),
        title="Module",
        summary="summary",
        order=0,
        sections=(_section(),),
    )


def _plan():
    return CourseSkeleton(
        topic="Python",
        modules=(
            ModuleSpec(title="M1", summary="s1", order=0),
            ModuleSpec(title="M2", summary="s2", order=1),
        ),
        sections=(),
        prerequisites=(),
    )


def _context():
    return GenerationContext(
        topic="Python",
        audience="beginner",
        difficulty="beginner",
        learning_outcomes=("Variables",),
    )


class TestRefinersCallLLM:

    def test_block_refiner_calls_llm_once(self):
        fake = FakeProvider(returns=make_block_response({"prompt": "new"}))
        agent = BlockRefinerAgent(_config(), fake)
        block = _block()
        agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_block": block,
            "section_outline": (),
            "issues": (make_issue(issue_id="i-1", scope="block", target_id=str(block.id)),),
            "context": None,
        })())
        assert fake.call_count == 1

    def test_section_refiner_calls_llm_once(self):
        fake = FakeProvider(returns=make_section_response("New Title", ["LO1", "LO2"]))
        agent = SectionRefinerAgent(_config(), fake)
        section = _section()
        agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_section": section,
            "module_outline": (),
            "issues": (make_issue(issue_id="i-1", scope="section", target_id=str(section.id)),),
            "context": None,
        })())
        assert fake.call_count == 1

    def test_module_refiner_calls_llm_once(self):
        fake = FakeProvider(returns=make_module_response("New Title", "new summary"))
        agent = ModuleRefinerAgent(_config(), fake)
        module = _module()
        agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_module": module,
            "course_outline": (),
            "issues": (make_issue(issue_id="i-1", scope="module", target_id=str(module.id)),),
            "context": None,
        })())
        assert fake.call_count == 1

    def test_context_refiner_calls_llm_once(self):
        fake = FakeProvider(returns=make_context_response(audience="engineer"))
        agent = ContextRefinerAgent(_config(), fake)
        ctx = _context()
        agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_context": ctx,
            "issues": (make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
            "user_feedback": "",
        })())
        assert fake.call_count == 1

    def test_prerequisites_refiner_calls_llm_once(self):
        fake = FakeProvider(
            returns=make_prereqs_response([{"from_topic": "a", "to_topic": "b", "type": "requires"}])
        )
        agent = PrerequisitesRefinerAgent(_config(), fake)
        agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_prerequisites": (),
            "issues": (make_issue(issue_id="i-1", scope="course", category="prerequisite"),),
            "course_topic": "Python",
        })())
        assert fake.call_count == 1

    def test_plan_refiner_calls_llm_once(self):
        fake = FakeProvider(returns=make_plan_response([]))
        agent = PlanRefinerAgent(_config(), fake)
        plan = _plan()
        agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_plan": plan,
            "issues": (make_issue(issue_id="i-1", scope="course", category="structural"),),
            "context": None,
            "constraints": (),
        })())
        assert fake.call_count == 1


class TestRefinersActuallyTransform:

    def test_block_refiner_applies_content(self):
        fake = FakeProvider(returns=make_block_response({"prompt": "new prompt", "hints": ["x", "y"]}))
        agent = BlockRefinerAgent(_config(), fake)
        block = _block()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_block": block,
            "section_outline": (),
            "issues": (make_issue(issue_id="i-1", scope="block", target_id=str(block.id)),),
            "context": None,
        })())
        assert out.block.content["prompt"] == "new prompt"
        assert out.block.content["hints"] == ["x", "y"]
        assert out.block.id == block.id
        assert out.block.version == block.version + 1

    def test_section_refiner_applies_title_and_objectives(self):
        fake = FakeProvider(returns=make_section_response("Renamed", ["LO1", "LO2"]))
        agent = SectionRefinerAgent(_config(), fake)
        section = _section()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_section": section,
            "module_outline": (),
            "issues": (make_issue(issue_id="i-1", scope="section", target_id=str(section.id)),),
            "context": None,
        })())
        assert out.section.title == "Renamed"
        assert out.section.learning_objectives == ["LO1", "LO2"]
        assert out.section.id == section.id

    def test_module_refiner_applies_title_and_summary(self):
        fake = FakeProvider(returns=make_module_response("New Module Title", "new summary text"))
        agent = ModuleRefinerAgent(_config(), fake)
        module = _module()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_module": module,
            "course_outline": (),
            "issues": (make_issue(issue_id="i-1", scope="module", target_id=str(module.id)),),
            "context": None,
        })())
        assert out.module.title == "New Module Title"
        assert out.module.summary == "new summary text"
        assert out.module.id == module.id

    def test_context_refiner_applies_audience(self):
        fake = FakeProvider(returns=make_context_response(audience="engineer"))
        agent = ContextRefinerAgent(_config(), fake)
        ctx = _context()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_context": ctx,
            "issues": (make_issue(issue_id="i-1", scope="course", category="audience_alignment"),),
            "user_feedback": "",
        })())
        assert out.context.audience == "engineer"
        assert out.context.topic == "Python"

    def test_prerequisites_refiner_applies_full_tuple(self):
        fake = FakeProvider(
            returns=make_prereqs_response([
                {"from_topic": "a", "to_topic": "b", "type": "requires"},
                {"from_topic": "b", "to_topic": "c", "type": "builds_on"},
            ])
        )
        agent = PrerequisitesRefinerAgent(_config(), fake)
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_prerequisites": (Prerequisite(from_topic="old", to_topic="old2"),),
            "issues": (make_issue(issue_id="i-1", scope="course", category="prerequisite"),),
            "course_topic": "Python",
        })())
        assert len(out.prerequisites) == 2
        assert out.prerequisites[0].from_topic == "a"
        assert out.prerequisites[1].type == "builds_on"

    def test_plan_refiner_merges_modules(self):
        fake = FakeProvider(returns=make_plan_response([
            {"title": "M1", "summary": "updated", "order": 0},
            {"title": "M3", "summary": "new", "order": 2},
        ]))
        agent = PlanRefinerAgent(_config(), fake)
        plan = _plan()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_plan": plan,
            "issues": (make_issue(issue_id="i-1", scope="course", category="structural"),),
            "context": None,
            "constraints": (),
        })())
        assert len(out.plan.modules) == 3
        titles = [m.title for m in out.plan.modules]
        assert "M1" in titles
        assert "M2" in titles
        assert "M3" in titles


class TestRefinersOutputTruncation:

    def test_block_refiner_raises_on_truncated(self):
        fake = FakeProvider(returns="this is not json at all")
        agent = BlockRefinerAgent(_config(), fake)
        with pytest.raises(RefinerOutputTruncated) as exc:
            agent.run(type("In", (), {
                "course_id": new_course_id(),
                "current_block": _block(),
                "section_outline": (),
                "issues": (make_issue(issue_id="i-1"),),
                "context": None,
            })())
        assert exc.value.level == "block"

    def test_section_refiner_raises_on_truncated(self):
        fake = FakeProvider(returns="{not closed")
        agent = SectionRefinerAgent(_config(), fake)
        with pytest.raises(RefinerOutputTruncated) as exc:
            agent.run(type("In", (), {
                "course_id": new_course_id(),
                "current_section": _section(),
                "module_outline": (),
                "issues": (make_issue(issue_id="i-1"),),
                "context": None,
            })())
        assert exc.value.level == "section"

    def test_module_refiner_raises_on_truncated(self):
        fake = FakeProvider(returns="truncated {")
        agent = ModuleRefinerAgent(_config(), fake)
        with pytest.raises(RefinerOutputTruncated):
            agent.run(type("In", (), {
                "course_id": new_course_id(),
                "current_module": _module(),
                "course_outline": (),
                "issues": (make_issue(issue_id="i-1"),),
                "context": None,
            })())

    def test_context_refiner_raises_on_truncated(self):
        fake = FakeProvider(returns="bad json")
        agent = ContextRefinerAgent(_config(), fake)
        with pytest.raises(RefinerOutputTruncated):
            agent.run(type("In", (), {
                "course_id": new_course_id(),
                "current_context": _context(),
                "issues": (make_issue(issue_id="i-1"),),
                "user_feedback": "",
            })())

    def test_prerequisites_refiner_raises_on_truncated(self):
        fake = FakeProvider(returns="{unclosed")
        agent = PrerequisitesRefinerAgent(_config(), fake)
        with pytest.raises(RefinerOutputTruncated):
            agent.run(type("In", (), {
                "course_id": new_course_id(),
                "current_prerequisites": (),
                "issues": (make_issue(issue_id="i-1"),),
                "course_topic": "Python",
            })())

    def test_plan_refiner_raises_on_truncated(self):
        fake = FakeProvider(returns="not json")
        agent = PlanRefinerAgent(_config(), fake)
        with pytest.raises(RefinerOutputTruncated):
            agent.run(type("In", (), {
                "course_id": new_course_id(),
                "current_plan": _plan(),
                "issues": (make_issue(issue_id="i-1"),),
                "context": None,
                "constraints": (),
            })())

    def test_schema_mismatch_raised_when_required_field_missing(self):
        fake = FakeProvider(returns='{"issues_addressed": ["i-1"]}')
        agent = BlockRefinerAgent(_config(), fake)
        with pytest.raises(RefinerSchemaMismatch) as exc:
            agent.run(type("In", (), {
                "course_id": new_course_id(),
                "current_block": _block(),
                "section_outline": (),
                "issues": (make_issue(issue_id="i-1"),),
                "context": None,
            })())
        assert "content" in exc.value.missing_fields


class TestRefinersTokensUsed:

    def test_block_refiner_records_tokens(self):
        fake = FakeProvider(returns=make_block_response({"prompt": "new"}))
        agent = BlockRefinerAgent(_config(), fake)
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_block": _block(),
            "section_outline": (),
            "issues": (make_issue(issue_id="i-1"),),
            "context": None,
        })())
        assert out.tokens_used is not None
        assert out.tokens_used.input_tokens >= 0

    def test_section_refiner_records_tokens(self):
        fake = FakeProvider(returns=make_section_response("T", ["LO"]))
        agent = SectionRefinerAgent(_config(), fake)
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_section": _section(),
            "module_outline": (),
            "issues": (make_issue(issue_id="i-1"),),
            "context": None,
        })())
        assert out.tokens_used is not None

    def test_module_refiner_records_tokens(self):
        fake = FakeProvider(returns=make_module_response("T", "S"))
        agent = ModuleRefinerAgent(_config(), fake)
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_module": _module(),
            "course_outline": (),
            "issues": (make_issue(issue_id="i-1"),),
            "context": None,
        })())
        assert out.tokens_used is not None

    def test_context_refiner_records_tokens(self):
        fake = FakeProvider(returns=make_context_response())
        agent = ContextRefinerAgent(_config(), fake)
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_context": _context(),
            "issues": (make_issue(issue_id="i-1"),),
            "user_feedback": "",
        })())
        assert out.tokens_used is not None

    def test_prerequisites_refiner_records_tokens(self):
        fake = FakeProvider(returns=make_prereqs_response([]))
        agent = PrerequisitesRefinerAgent(_config(), fake)
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_prerequisites": (),
            "issues": (make_issue(issue_id="i-1"),),
            "course_topic": "Python",
        })())
        assert out.tokens_used is not None

    def test_plan_refiner_records_tokens(self):
        fake = FakeProvider(returns=make_plan_response([]))
        agent = PlanRefinerAgent(_config(), fake)
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_plan": _plan(),
            "issues": (make_issue(issue_id="i-1"),),
            "context": None,
            "constraints": (),
        })())
        assert out.tokens_used is not None


class TestPlanRefinerMergeD8:

    def test_merge_adds_new_modules(self):
        current = CourseSkeleton(
            topic="Python",
            modules=(ModuleSpec(title="M1", summary="", order=0),),
            sections=(),
            prerequisites=(),
        )
        llm_modules = [
            {"title": "M1", "summary": "updated", "order": 0},
            {"title": "M2", "summary": "new", "order": 1},
        ]
        merged, affected = merge_plan(current, llm_modules)
        assert len(merged) == 2
        assert merged[0].title == "M1"
        assert merged[1].title == "M2"
        assert 1 in affected

    def test_merge_keeps_removed_modules(self):
        current = CourseSkeleton(
            topic="Python",
            modules=(
                ModuleSpec(title="M1", summary="", order=0),
                ModuleSpec(title="M2", summary="", order=1),
            ),
            sections=(),
            prerequisites=(),
        )
        llm_modules = [
            {"title": "M1", "summary": "only M1", "order": 0},
        ]
        merged, affected = merge_plan(current, llm_modules)
        assert len(merged) == 2
        titles = [m.title for m in merged]
        assert "M1" in titles
        assert "M2" in titles

    def test_merge_handles_empty_llm_output(self):
        current = CourseSkeleton(
            topic="Python",
            modules=(ModuleSpec(title="M1", summary="", order=0),),
            sections=(),
            prerequisites=(),
        )
        merged, affected = merge_plan(current, [])
        assert len(merged) == 1
        assert affected == ()

    def test_merge_deduplicates_by_title(self):
        current = CourseSkeleton(
            topic="Python",
            modules=(ModuleSpec(title="M1", summary="", order=0),),
            sections=(),
            prerequisites=(),
        )
        llm_modules = [
            {"title": "M1", "summary": "v1", "order": 0},
            {"title": "M1", "summary": "v2", "order": 0},
        ]
        merged, affected = merge_plan(current, llm_modules)
        assert len(merged) == 1
        assert merged[0].summary in ("v1", "v2")


class TestRefinersD11Immutability:

    def test_block_refiner_preserves_id(self):
        fake = FakeProvider(returns=make_block_response({"prompt": "new"}))
        agent = BlockRefinerAgent(_config(), fake)
        block = _block()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_block": block,
            "section_outline": (),
            "issues": (make_issue(issue_id="i-1"),),
            "context": None,
        })())
        assert out.block.id == block.id
        assert out.block.type == block.type
        assert out.block.order == block.order

    def test_section_refiner_preserves_blocks(self):
        fake = FakeProvider(returns=make_section_response("T", ["LO"]))
        agent = SectionRefinerAgent(_config(), fake)
        section = _section()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_section": section,
            "module_outline": (),
            "issues": (make_issue(issue_id="i-1"),),
            "context": None,
        })())
        assert out.section.id == section.id
        assert len(out.section.blocks) == len(section.blocks)

    def test_module_refiner_preserves_sections(self):
        fake = FakeProvider(returns=make_module_response("T", "S"))
        agent = ModuleRefinerAgent(_config(), fake)
        module = _module()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_module": module,
            "course_outline": (),
            "issues": (make_issue(issue_id="i-1"),),
            "context": None,
        })())
        assert out.module.id == module.id
        assert len(out.module.sections) == len(module.sections)

    def test_context_refiner_preserves_topic(self):
        fake = FakeProvider(returns=make_context_response())
        agent = ContextRefinerAgent(_config(), fake)
        ctx = _context()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_context": ctx,
            "issues": (make_issue(issue_id="i-1"),),
            "user_feedback": "",
        })())
        assert out.context.topic == ctx.topic

    def test_context_refiner_validates_audience_enum(self):
        fake = FakeProvider(returns='{"audience": "invalid_value", "issues_addressed": ["i-1"]}')
        agent = ContextRefinerAgent(_config(), fake)
        ctx = _context()
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_context": ctx,
            "issues": (make_issue(issue_id="i-1"),),
            "user_feedback": "",
        })())
        assert out.context.audience == ctx.audience

    def test_prerequisites_refiner_skips_invalid_entries(self):
        fake = FakeProvider(returns=make_prereqs_response([
            {"from_topic": "", "to_topic": "b"},
            {"from_topic": "a", "to_topic": ""},
            {"from_topic": "a", "to_topic": "b"},
            {"from_topic": "x", "to_topic": "y", "type": "invalid_type"},
        ]))
        agent = PrerequisitesRefinerAgent(_config(), fake)
        out = agent.run(type("In", (), {
            "course_id": new_course_id(),
            "current_prerequisites": (),
            "issues": (make_issue(issue_id="i-1"),),
            "course_topic": "Python",
        })())
        assert len(out.prerequisites) == 2
        assert out.prerequisites[0].from_topic == "a"
        assert out.prerequisites[1].type == "requires"


class TestRefinersPromptRegistry:

    def test_all_refiners_have_prompts(self):
        from cogenai.prompt import get_prompt as yaml_get_prompt
        for name in (
            "context_refiner",
            "prerequisites_refiner",
            "plan_refiner",
            "module_refiner",
            "section_refiner",
            "block_refiner",
        ):
            bundle = yaml_get_prompt(name, "1.0.0")
            assert bundle is not None, f"missing YAML prompt for {name}"
            assert "OUTPUT RULES" in bundle.system_prompt
