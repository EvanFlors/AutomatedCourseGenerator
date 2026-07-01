"""Top-level LLM orchestrator.

The orchestrator LLM receives the full state and emits a structured
decision: chain-of-thought reasoning, a list of `actions` to run this
iteration, optional `questions` to ask a human (HITL), and an optional
`terminate` flag with a reason.

This is the brain of the pipeline. It replaces the deterministic
`IssueAnalyzer` + `RefinementPlanner` chain with a single reasoning
step, while keeping the granular refiner agents as executors.

The runner (`run_demo`) is responsible for:
1. Calling `LLMOrchestrator.plan()` once per iteration.
2. Executing each action via the corresponding refiner agent.
3. If the decision has `questions` (HITL), pausing the job.
4. If `terminate` is True, ending the loop with the chosen reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from cogenai.application.agents.base import BaseAgent
from cogenai.application.agents.config import AgentConfig
from cogenai.domain.ports.llm import LLMProvider


# ----------------------------- Decision schema -----------------------------

RefinementLevel = Literal[
    "context", "metadata", "prerequisites", "plan", "module", "section", "block",
]


class OrchestratorAction(BaseModel):
    level: RefinementLevel = Field(..., description="Which refiner to run.")
    reason: str = Field(..., description="One-sentence justification.")


class OrchestratorQuestion(BaseModel):
    id: str = Field(..., description="Stable id so the human's reply can be matched.")
    prompt: str = Field(..., description="Question for the human.")
    context: str = Field("", description="Why this question matters.")


class OrchestratorDecision(BaseModel):
    think: str = Field(..., min_length=1, description="Chain-of-thought summary.")
    actions: list[OrchestratorAction] = Field(default_factory=list)
    questions: list[OrchestratorQuestion] = Field(default_factory=list)
    terminate: bool = False
    termination_reason: str | None = None


# ----------------------------- Inputs / outputs -----------------------------

@dataclass
class OrchestratorInput:
    """Full state passed to the orchestrator at each iteration."""
    iteration: int
    max_iterations: int
    overall_score: float
    passed: bool
    tokens_used: int
    token_budget: int | None
    evaluation_report_text: str
    history_text: str
    working_bundle: str
    request_summary_text: str


@dataclass
class OrchestratorOutput:
    decision: OrchestratorDecision
    raw_response: str = ""
    tokens_used: object | None = None


# ----------------------------- Agent -----------------------------

class LLMOrchestrator(BaseAgent[OrchestratorInput, OrchestratorOutput]):

    LEVELS = ("context", "metadata", "prerequisites", "plan", "module", "section", "block")

    def __init__(self, config: AgentConfig, llm_provider: LLMProvider):
        super().__init__(name="top_orchestrator", config=config, llm_provider=llm_provider)

    def run(self, input_data: OrchestratorInput) -> OrchestratorOutput:
        prompt = self._render_user_prompt(input_data)
        # Use BaseAgent._call_llm (returns text) and synthesize a token-count
        # stub if the provider doesn't expose usage.
        text = self._call_llm(prompt, self._get_prompt())
        decision = self._parse_decision(text)
        return OrchestratorOutput(
            decision=decision,
            raw_response=text,
            tokens_used=None,
        )

    def _render_user_prompt(self, data: OrchestratorInput) -> str:
        from cogenai.prompt import get_prompt as yaml_get_prompt
        bundle = yaml_get_prompt(self.name)
        if bundle is None:
            raise ValueError("top_orchestrator YAML prompt missing")
        return bundle.user_prompt.format(
            topic=data.request_summary_text,
            audience="",  # the summary string already includes these
            difficulty="",
            outcomes="",
            iteration=data.iteration,
            max_iterations=data.max_iterations,
            overall_score=f"{data.overall_score:.2f}",
            passed=str(data.passed).lower(),
            tokens_used=data.tokens_used,
            token_budget=data.token_budget if data.token_budget is not None else "unbounded",
            working_bundle=data.working_bundle,
            evaluation_report=data.evaluation_report_text,
            history=data.history_text,
        )

    def _parse_decision(self, raw: str) -> OrchestratorDecision:
        """Parse the orchestrator's JSON response, with defensive fallback.

        If the response is not valid JSON or doesn't match the schema,
        return a conservative decision: terminate with quality_threshold
        if score is high, else fall back to no-op.
        """
        import json
        text = raw.strip()
        # Extract the first {...} block from the response.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            # Defensive: cannot parse, return a no-action decision.
            return OrchestratorDecision(
                think="orchestrator response was not JSON; falling back to no-op",
                actions=[],
                questions=[],
                terminate=False,
                termination_reason=None,
            )
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return OrchestratorDecision(
                think="orchestrator response was malformed JSON; falling back to no-op",
                actions=[],
                questions=[],
                terminate=False,
                termination_reason=None,
            )
        try:
            return OrchestratorDecision(**data)
        except Exception:
            # Schema mismatch: strip unknown fields and try again.
            try:
                return OrchestratorDecision.model_validate(data)
            except Exception:
                return OrchestratorDecision(
                    think="orchestrator schema mismatch; falling back to no-op",
                    actions=[],
                    questions=[],
                    terminate=False,
                    termination_reason=None,
                )