from __future__ import annotations

from cogenai.application.agents.config import AgentAssignmentPolicy, AgentConfig


class TestAgentAssignmentPolicy:
    def test_default_returns_default_model(self):
        policy = AgentAssignmentPolicy(default_model="stub")
        assert policy.resolve("any_role") == "stub"

    def test_role_override_takes_precedence(self):
        policy = AgentAssignmentPolicy(
            default_model="stub",
            role_models={"evaluator": "gpt-4"},
        )
        assert policy.resolve("evaluator") == "gpt-4"
        assert policy.resolve("other") == "stub"

    def test_with_override_is_immutable(self):
        policy = AgentAssignmentPolicy(default_model="stub")
        policy2 = policy.with_override("refiner", "gpt-4-mini")
        assert policy.resolve("refiner") == "stub"
        assert policy2.resolve("refiner") == "gpt-4-mini"

    def test_with_override_preserves_existing(self):
        policy = AgentAssignmentPolicy(
            default_model="stub",
            role_models={"evaluator": "gpt-4"},
        )
        policy2 = policy.with_override("refiner", "gpt-4-mini")
        assert policy2.resolve("evaluator") == "gpt-4"
        assert policy2.resolve("refiner") == "gpt-4-mini"


class TestAgentConfigModelFor:
    def test_default_model_when_no_override(self):
        cfg = AgentConfig.default(model_name="stub")
        assert cfg.model_for("any").name == "stub"
        assert cfg.model_for("evaluator").name == "stub"

    def test_per_role_override(self):
        policy = AgentAssignmentPolicy(
            default_model="stub",
            role_models={"evaluator": "gpt-4", "refiner": "gpt-4-mini"},
        )
        cfg = AgentConfig.default(model_name="stub", assignments=policy)
        assert cfg.model_for("evaluator").name == "gpt-4"
        assert cfg.model_for("refiner").name == "gpt-4-mini"
        assert cfg.model_for("other").name == "stub"

    def test_config_is_frozen(self):
        import pytest
        cfg = AgentConfig.default(model_name="stub")
        with pytest.raises(Exception):
            cfg.model = "x"  # type: ignore[misc]


class TestGenerationRequestAgentAssignments:
    def test_default_none(self):
        from cogenai.interfaces.dto.generation_request import GenerationRequestDTO
        r = GenerationRequestDTO(topic="x", learning_outcomes=("a",))
        assert r.agent_assignments is None

    def test_assignments_round_trip(self):
        from cogenai.interfaces.dto.generation_request import GenerationRequestDTO
        r = GenerationRequestDTO(
            topic="x",
            learning_outcomes=("a",),
            agent_assignments={"evaluator": "gpt-4"},
        )
        assert r.agent_assignments == {"evaluator": "gpt-4"}