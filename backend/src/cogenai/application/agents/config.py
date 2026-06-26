from __future__ import annotations

from dataclasses import dataclass, field

from cogenai.domain.value_objects.llm import Model


@dataclass(frozen=True)
class AgentAssignmentPolicy:
    """Per-agent-role model overrides per FR-AG-014.

    Maps a role name (matching `BaseAgent.name`) to a model identifier.
    Falls back to `default_model` when a role is not explicitly assigned.
    """

    role_models: dict[str, str] = field(default_factory=dict)
    default_model: str = "stub"

    def resolve(self, role: str) -> str:
        return self.role_models.get(role, self.default_model)

    def with_override(self, role: str, model_name: str) -> "AgentAssignmentPolicy":
        merged = dict(self.role_models)
        merged[role] = model_name
        return AgentAssignmentPolicy(role_models=merged, default_model=self.default_model)


@dataclass(frozen=True)
class AgentConfig:

    model: Model
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    tools: tuple[str, ...] = field(default_factory=tuple)
    max_retries: int = 3
    assignments: AgentAssignmentPolicy = field(default_factory=AgentAssignmentPolicy)

    def __post_init__(self):
        if self.temperature < 0 or self.temperature > 1:
            raise ValueError("Temperature must be between 0 and 1.")
        if self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive.")

    def model_for(self, role: str) -> Model:
        """Return the model to use for a given agent role.

        If a per-role override exists in `assignments`, return it; otherwise
        fall back to the default model. The role name matches `BaseAgent.name`.
        """
        name = self.assignments.resolve(role)
        return Model(name=name)

    @classmethod
    def default(
        cls,
        model_name: str = "gemini-2.5-flash",
        assignments: AgentAssignmentPolicy | None = None,
    ) -> AgentConfig:
        policy = assignments or AgentAssignmentPolicy(default_model=model_name)
        return cls(
            model=Model(name=model_name),
            temperature=0.7,
            max_tokens=2048,
            assignments=policy,
        )