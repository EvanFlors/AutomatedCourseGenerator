from __future__ import annotations

import json

import pytest

from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.top_orchestrator import (
    LLMOrchestrator,
    OrchestratorAction,
    OrchestratorDecision,
    OrchestratorInput,
    OrchestratorQuestion,
)
from cogenai.domain.value_objects.llm import (
    CompletionResponse,
    CompletionUsage,
)


class _StubProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def health_check(self) -> bool:
        return True

    def complete(self, request):
        return CompletionResponse(
            text=self.response_text,
            model=request.model,
            usage=CompletionUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            finish_reason="stop",
        )


def _config() -> AgentConfig:
    return AgentConfig.default(model_name="stub")


def _input(**overrides) -> OrchestratorInput:
    base = dict(
        iteration=1,
        max_iterations=3,
        overall_score=0.6,
        passed=False,
        tokens_used=100,
        token_budget=10_000,
        evaluation_report_text="accuracy: 0.7, structure: 0.5",
        history_text="(no prior iterations)",
        working_bundle="CourseBundle(...)",
        request_summary_text="topic=Python audience=beginner",
    )
    base.update(overrides)
    return OrchestratorInput(**base)


class TestOrchestratorDecision:
    def test_default_decision_is_empty_actions(self):
        d = OrchestratorDecision(think="t")
        assert d.actions == []
        assert d.questions == []
        assert d.terminate is False
        assert d.termination_reason is None

    def test_decision_with_actions(self):
        d = OrchestratorDecision(
            think="context fix needed",
            actions=[OrchestratorAction(level="context", reason="bad audience")],
            terminate=False,
        )
        assert len(d.actions) == 1
        assert d.actions[0].level == "context"

    def test_decision_with_questions(self):
        d = OrchestratorDecision(
            think="needs clarification",
            questions=[OrchestratorQuestion(
                id="q1", prompt="What audience?", context="ambiguous topic",
            )],
            terminate=True,
            termination_reason="user_aborted",
        )
        assert len(d.questions) == 1
        assert d.questions[0].id == "q1"
        assert d.terminate is True


class TestLLMOrchestratorParseDecision:
    def test_parses_well_formed_json(self):
        raw = json.dumps({
            "think": "test",
            "actions": [{"level": "context", "reason": "fix audience"}],
            "questions": [],
            "terminate": False,
        })
        agent = LLMOrchestrator(_config(), _StubProvider(""))
        decision = agent._parse_decision(raw)
        assert decision.think == "test"
        assert len(decision.actions) == 1
        assert decision.actions[0].level == "context"

    def test_extracts_json_from_prose(self):
        raw = (
            "Here is my plan:\n"
            "```json\n" +
            json.dumps({
                "think": "embedded",
                "actions": [],
                "questions": [],
                "terminate": True,
                "termination_reason": "quality_threshold",
            }) +
            "\n```\n"
        )
        agent = LLMOrchestrator(_config(), _StubProvider(""))
        decision = agent._parse_decision(raw)
        assert decision.think == "embedded"
        assert decision.terminate is True
        assert decision.termination_reason == "quality_threshold"

    def test_invalid_json_returns_safe_default(self):
        agent = LLMOrchestrator(_config(), _StubProvider(""))
        decision = agent._parse_decision("not json at all")
        assert decision.actions == []
        assert decision.questions == []
        assert decision.terminate is False

    def test_schema_mismatch_returns_safe_default(self):
        # `level` is invalid; Pydantic should reject.
        raw = json.dumps({
            "think": "t",
            "actions": [{"level": "nonexistent", "reason": "x"}],
        })
        agent = LLMOrchestrator(_config(), _StubProvider(""))
        decision = agent._parse_decision(raw)
        assert decision.actions == []  # safe default


class TestLLMOrchestratorRun:
    def test_run_returns_decision_from_llm(self):
        provider = _StubProvider(json.dumps({
            "think": "fix plan",
            "actions": [{"level": "plan", "reason": "structure"}],
            "questions": [],
            "terminate": False,
        }))
        agent = LLMOrchestrator(_config(), provider)
        output = agent.run(_input())
        assert output.decision.think == "fix plan"
        assert output.decision.actions[0].level == "plan"
        assert output.raw_response  # echoed back
        # Token accounting is done by the runner, not the agent itself.

    def test_run_with_question_pauses(self):
        provider = _StubProvider(json.dumps({
            "think": "need human input",
            "actions": [],
            "questions": [{"id": "q1", "prompt": "Audience?", "context": "ambiguous"}],
            "terminate": False,
        }))
        agent = LLMOrchestrator(_config(), provider)
        output = agent.run(_input())
        assert len(output.decision.questions) == 1
        assert output.decision.questions[0].id == "q1"

    def test_run_with_terminate(self):
        provider = _StubProvider(json.dumps({
            "think": "passed, done",
            "actions": [],
            "questions": [],
            "terminate": True,
            "termination_reason": "quality_threshold",
        }))
        agent = LLMOrchestrator(_config(), provider)
        output = agent.run(_input())
        assert output.decision.terminate is True
        assert output.decision.termination_reason == "quality_threshold"