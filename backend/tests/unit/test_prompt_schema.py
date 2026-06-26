from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from cogenai.application.agents.config import AgentConfig
from cogenai.application.agents.base import BaseAgent
from cogenai.bootstrap.logging import get_logger
from cogenai.domain.ports.llm import LLMProvider
from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage
from cogenai.prompt import (
    PromptBundle,
    get_prompt,
    has_prompt,
    load_prompts,
    render_schema_instruction,
)

logger = get_logger(__name__)


class _StubProvider:
    """Captures the last CompletionRequest for inspection."""

    def __init__(self):
        self.last_request = None

    def health_check(self) -> bool:
        return True

    def complete(self, request) -> CompletionResponse:
        self.last_request = request
        return CompletionResponse(
            text='{"ok": true}',
            model=request.model,
            usage=CompletionUsage(0, 0, 0),
            finish_reason="stop",
        )


class TestPromptBundleSchema:
    def test_default_schema_is_none(self):
        bundle = PromptBundle(
            name="x", version="1.0.0", description="",
            system_prompt="", user_prompt="",
        )
        assert bundle.schema is None
        assert bundle.has_schema() is False

    def test_has_schema_true_when_present(self):
        bundle = PromptBundle(
            name="x", version="1.0.0", description="",
            system_prompt="", user_prompt="",
            schema={"type": "object"},
        )
        assert bundle.has_schema() is True


class TestYamlLoaderSchema:
    def test_yaml_without_schema_loads_with_none(self, tmp_path):
        f = tmp_path / "no_schema.yml"
        f.write_text(yaml.safe_dump({
            "name": "no_schema",
            "version": "1.0.0",
            "system_prompt": "hi",
        }))
        load_prompts(tmp_path)
        b = get_prompt("no_schema")
        assert b is not None
        assert b.schema is None

    def test_yaml_with_schema_loads(self, tmp_path):
        f = tmp_path / "with_schema.yml"
        f.write_text(yaml.safe_dump({
            "name": "with_schema",
            "version": "1.0.0",
            "system_prompt": "hi",
            "schema": {"type": "object", "properties": {"x": {"type": "integer"}}},
        }))
        load_prompts(tmp_path)
        b = get_prompt("with_schema")
        assert b is not None
        assert b.schema == {"type": "object", "properties": {"x": {"type": "integer"}}}

    def test_yaml_with_non_dict_schema_raises(self, tmp_path):
        f = tmp_path / "bad_schema.yml"
        f.write_text(yaml.safe_dump({
            "name": "bad",
            "version": "1.0.0",
            "system_prompt": "hi",
            "schema": "not-a-dict",
        }))
        with pytest.raises(ValueError, match="must be a mapping"):
            load_prompts(tmp_path)

    def test_built_in_refiners_have_schemas(self):
        # The 7 refiner YAMLs shipped with schemas in this sprint.
        for name in (
            "context_refiner", "prerequisites_refiner", "plan_refiner",
            "module_refiner", "section_refiner", "block_refiner",
            "metadata_refiner", "evaluator",
        ):
            bundle = get_prompt(name)
            assert bundle is not None, f"missing prompt for {name}"
            assert bundle.has_schema(), f"{name} is missing a schema"


class TestRenderSchemaInstruction:
    def test_renders_valid_json(self):
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        out = render_schema_instruction(schema)
        assert "OUTPUT SCHEMA" in out
        assert "\"type\": \"object\"" in out
        assert "```json" in out
        # Should be parseable JSON inside the fence
        import re
        m = re.search(r"```json\n(.*?)\n```", out, re.DOTALL)
        assert m is not None
        parsed = yaml.safe_load(m.group(1))
        assert parsed == schema


class TestBaseAgentSchemaInjection:
    def test_call_llm_without_bundle_no_schema_injection(self):
        provider = _StubProvider()
        agent = _make_agent(provider)
        agent._call_llm("hello", system_prompt="BASE")
        req = provider.last_request
        assert req is not None
        assert req.output_schema is None
        assert req.system_prompt == "BASE"

    def test_call_llm_with_bundle_injects_schema_into_system(self):
        provider = _StubProvider()
        agent = _make_agent(provider)
        bundle = PromptBundle(
            name="x", version="1.0.0", description="",
            system_prompt="ORIG",
            user_prompt="",
            schema={"type": "object", "properties": {"y": {"type": "string"}}},
        )
        agent._call_llm("hello", system_prompt="ORIG", bundle=bundle)
        req = provider.last_request
        assert req.output_schema == bundle.schema
        assert "ORIG" in req.system_prompt
        assert "OUTPUT SCHEMA" in req.system_prompt
        assert "\"y\"" in req.system_prompt

    def test_get_prompt_bundle_returns_schema(self):
        provider = _StubProvider()
        # Use a real agent name that ships with a schema in Sprint 6.
        agent = _make_agent(provider, name="context_refiner")
        bundle = agent._get_prompt_bundle()
        assert bundle.has_schema()
        assert bundle.schema["type"] == "object"


def _make_agent(provider, name: str = "stub_agent") -> BaseAgent:
    cfg = AgentConfig.default(model_name="stub")
    return _StubAgent(name=name, config=cfg, llm_provider=provider)


from dataclasses import dataclass


@dataclass
class _StubAgent(BaseAgent):
    """Minimal BaseAgent subclass for testing."""
    name: str = "stub_agent"
    config: AgentConfig = None
    llm_provider: LLMProvider = None

    def run(self, input_data):
        return None


# Patch dataclass-based field defaults
_StubAgent.__dataclass_fields__["config"].default = AgentConfig.default(model_name="stub")
_StubAgent.__dataclass_fields__["llm_provider"].default = None