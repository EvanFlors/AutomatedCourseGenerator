from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AudienceLiteral = Literal[
    "beginner", "professional", "engineer", "architect",
    "manager", "researcher", "student",
]
DifficultyLiteral = Literal["beginner", "intermediate", "advanced", "expert"]


class GenerationRequestDTO(BaseModel):
    """Validated input for the multi-agent generation pipeline.

    Replaces the untyped `dict[str, Any]` that used to be passed between
    the CLI and the orchestrator. Frozen: any "mutation" is done via
    `model_copy(update={...})`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic: str = Field(..., min_length=1, description="Course topic.")
    audience: AudienceLiteral = "beginner"
    difficulty: DifficultyLiteral = "beginner"
    learning_outcomes: tuple[str, ...] = Field(..., min_length=1)

    text_instructions: str = ""
    strategy: str = "fundamental learning"
    block_types: tuple[str, ...] = ("concept", "example", "exercise")

    num_modules: int = Field(1, ge=1, le=20)
    sections_per_module: int = Field(1, ge=1, le=10)
    blocks_per_section: int = Field(3, ge=1, le=20)

    max_iterations: int = Field(3, ge=1, le=20)
    max_modules: int | None = Field(None, ge=1, le=20)
    max_sections_per_module: int | None = Field(None, ge=1, le=10)
    max_blocks_per_section: int | None = Field(None, ge=1, le=20)
    token_budget: int | None = Field(
        None, ge=1_000,
        description="Per-job token cap (input+output). When None, settings.token_budget_input + output is used.",
    )
    agent_assignments: dict[str, str] | None = Field(
        None,
        description="Per-agent-role model overrides (FR-AG-014). Keys are BaseAgent.name values.",
    )

    def effective_token_budget(self, fallback: int) -> int:
        """Return the token budget, falling back to `fallback` (e.g., settings default)."""
        return int(self.token_budget) if self.token_budget is not None else int(fallback)

    @field_validator("learning_outcomes", "block_types", mode="before")
    @classmethod
    def _coerce_to_tuple(cls, v: Any) -> tuple:
        if v is None:
            return ()
        if isinstance(v, str):
            return (v,)
        return tuple(v)

    @field_validator("learning_outcomes")
    @classmethod
    def _strip_empty_outcomes(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(o for o in v if o and o.strip())

    @classmethod
    def default(cls) -> "GenerationRequestDTO":
        return cls(
            topic="Python",
            audience="beginner",
            difficulty="beginner",
            learning_outcomes=("Variables", "Data Types"),
        )

    def with_updates(self, **overrides: Any) -> "GenerationRequestDTO":
        return self.model_copy(update=overrides)
