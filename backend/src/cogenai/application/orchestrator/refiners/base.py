from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar

from cogenai.application.agents.base import BaseAgent
from cogenai.application.agents.config import AgentConfig
from cogenai.domain.course import ContentBlock, Course, Module, Section
from cogenai.domain.shared.value_objects import BlockId, CourseId, ModuleId, SectionId

RefinementLevel = Literal["context", "metadata", "prerequisites", "plan", "module", "section", "block"]

Input = TypeVar("Input")
Output = TypeVar("Output")


@dataclass(frozen=True)
class RefinementScope:
    level: RefinementLevel
    target_id: str
    parent_refs: dict[str, str] = field(default_factory=dict)
    sibling_summaries: dict[str, str] = field(default_factory=dict)
    issue_ids: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    pass_rate: float = 0.8


@dataclass(frozen=True)
class TokenCapExceeded(Exception):
    level: RefinementLevel
    estimated_tokens: int
    cap: int

    def __str__(self) -> str:
        return (
            f"Token cap exceeded for level={self.level} "
            f"({self.estimated_tokens} > {self.cap})"
        )


@dataclass(frozen=True)
class ContextRefinerInput:
    course_id: CourseId
    current_context: "cogenai.application.orchestrator.context_synthesizer.GenerationContext"
    issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...]
    user_feedback: str = ""
    # Full evaluation report (all levels) for richer context.
    # `issues` above is the level-filtered slice; this is the whole picture.
    all_issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    previous_iteration_summary: str = ""


@dataclass(frozen=True)
class ContextRefinerOutput:
    context: "cogenai.application.orchestrator.context_synthesizer.GenerationContext"
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)
    issues_residual: tuple[str, ...] = field(default_factory=tuple)
    refinement_notes: str = ""
    tokens_used: object | None = None


@dataclass(frozen=True)
class PrerequisitesRefinerInput:
    course_id: CourseId
    current_prerequisites: tuple["cogenai.application.orchestrator.curriculum_planner.Prerequisite", ...]
    issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...]
    course_topic: str = ""
    all_issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    previous_iteration_summary: str = ""


@dataclass(frozen=True)
class PrerequisitesRefinerOutput:
    prerequisites: tuple["cogenai.application.orchestrator.curriculum_planner.Prerequisite", ...]
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)
    issues_residual: tuple[str, ...] = field(default_factory=tuple)
    refinement_notes: str = ""
    tokens_used: object | None = None


@dataclass(frozen=True)
class PlanRefinerInput:
    course_id: CourseId
    current_plan: "cogenai.application.orchestrator.curriculum_planner.CourseSkeleton"
    issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...]
    context: "cogenai.application.orchestrator.context_synthesizer.GenerationContext"
    constraints: tuple[str, ...] = field(default_factory=tuple)
    all_issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    previous_iteration_summary: str = ""


@dataclass(frozen=True)
class PlanRefinerOutput:
    plan: "cogenai.application.orchestrator.curriculum_planner.CourseSkeleton"
    affected_module_ids: tuple[int, ...] = field(default_factory=tuple)
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)
    issues_residual: tuple[str, ...] = field(default_factory=tuple)
    refinement_notes: str = ""
    tokens_used: object | None = None


@dataclass(frozen=True)
class ModuleRefinerInput:
    course_id: CourseId
    current_module: Module
    course_outline: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    context: "cogenai.application.orchestrator.context_synthesizer.GenerationContext" | None = None
    all_issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    previous_iteration_summary: str = ""


@dataclass(frozen=True)
class ModuleRefinerOutput:
    module: Module
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)
    issues_residual: tuple[str, ...] = field(default_factory=tuple)
    refinement_notes: str = ""
    tokens_used: object | None = None


@dataclass(frozen=True)
class SectionRefinerInput:
    course_id: CourseId
    current_section: Section
    module_outline: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    context: "cogenai.application.orchestrator.context_synthesizer.GenerationContext" | None = None
    all_issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    previous_iteration_summary: str = ""


@dataclass(frozen=True)
class SectionRefinerOutput:
    section: Section
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)
    issues_residual: tuple[str, ...] = field(default_factory=tuple)
    refinement_notes: str = ""
    tokens_used: object | None = None


@dataclass(frozen=True)
class BlockRefinerInput:
    course_id: CourseId
    current_block: ContentBlock
    section_outline: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    context: "cogenai.application.orchestrator.context_synthesizer.GenerationContext" | None = None
    all_issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = field(default_factory=tuple)
    previous_iteration_summary: str = ""


@dataclass(frozen=True)
class BlockRefinerOutput:
    block: ContentBlock
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)
    issues_residual: tuple[str, ...] = field(default_factory=tuple)
    refinement_notes: str = ""
    tokens_used: object | None = None


@dataclass(frozen=True)
class MetadataRefinerInput:
    course_id: CourseId
    current_tags: tuple[str, ...]
    current_language: str
    current_duration_minutes: int
    topic: str = ""
    audience: str = ""
    difficulty: str = ""
    issues: tuple["cogenai.application.orchestrator.evaluator.EvaluationIssue", ...] = ()


@dataclass(frozen=True)
class MetadataRefinerOutput:
    tags: tuple[str, ...]
    language: str
    estimated_duration_minutes: int
    issues_addressed: tuple[str, ...] = field(default_factory=tuple)
    refinement_notes: str = ""
    tokens_used: object | None = None


def parse_json_response(response: str, level: RefinementLevel) -> dict:
    """Match first {...}, parse JSON. Raise RefinerOutputTruncated on failure."""
    from cogenai.application.orchestrator.refiners.exceptions import RefinerOutputTruncated

    match = re.search(r"\{.*\}", response, re.DOTALL)
    if not match:
        estimated = len(response) // 4
        raise RefinerOutputTruncated(
            level=level,
            raw_response_preview=response[:200],
            estimated_tokens=estimated,
        )
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as exc:
        estimated = len(response) // 4
        raise RefinerOutputTruncated(
            level=level,
            raw_response_preview=response[:200],
            estimated_tokens=estimated,
        ) from exc


def validate_fields(
    parsed: dict,
    required: tuple[str, ...],
    level: RefinementLevel,
) -> None:
    """Raise RefinerSchemaMismatch if any required field is missing."""
    from cogenai.application.orchestrator.refiners.exceptions import RefinerSchemaMismatch

    missing = tuple(field for field in required if field not in parsed)
    if missing:
        raise RefinerSchemaMismatch(level=level, missing_fields=missing)


def extract_tokens(response) -> object | None:
    """Pull usage from the LLM response; return None if unavailable."""
    return getattr(response, "usage", None)


class BaseRefiner(BaseAgent[Input, Output], Generic[Input, Output]):

    TOKEN_CAP: int = 1000
    LEVEL: RefinementLevel = "block"

    def __init__(self, name: str, config: AgentConfig, llm_provider):
        super().__init__(name=name, config=config, llm_provider=llm_provider)

    def _call_llm_full(
        self,
        prompt: str,
        system_prompt: str = "",
        bundle=None,
    ):
        """Call the LLM and return the full CompletionResponse (incl. usage).

        Overrides BaseAgent._call_llm so refiners can record token usage
        and forward the response object to the helpers. If `bundle` (a
        `PromptBundle`) carries a schema, it is injected into the system
        prompt AND passed as `output_schema` for providers that support it.
        """
        from cogenai.domain.value_objects.llm import CompletionRequest
        final_system = self._build_system_prompt(system_prompt, bundle)
        request = CompletionRequest(
            prompt=prompt,
            model=self.config.model_for(self.name),
            system_prompt=final_system,
            output_schema=bundle.schema if bundle else None,
        )
        return self.llm_provider.complete(request)

    def _build_prompt(
        self,
        scope: RefinementScope,
        bundle: dict,
        issue_text: str,
    ) -> str:
        lines = [
            f"Refine {scope.level} (target_id={scope.target_id}).",
            f"Pass rate threshold: {scope.pass_rate:.2f}",
            "",
            "Context bundle:",
        ]
        for key, value in bundle.items():
            lines.append(f"- {key}: {value}")
        if scope.constraints:
            lines.append("")
            lines.append("Constraints:")
            for c in scope.constraints:
                lines.append(f"- {c}")
        if issue_text:
            lines.append("")
            lines.append("Issues to address:")
            lines.append(issue_text)
        return "\n".join(lines)

    def estimate_tokens(self, prompt: str) -> int:
        return len(prompt) // 4
