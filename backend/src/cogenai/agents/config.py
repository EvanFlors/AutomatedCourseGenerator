from __future__ import annotations

from dataclasses import dataclass, field

from cogenai.domain.value_objects.llm import Model


@dataclass(frozen=True)
class AgentConfig:

    model: Model
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    tools: tuple[str, ...] = field(default_factory=tuple)
    max_retries: int = 3

    def __post_init__(self):
        if self.temperature < 0 or self.temperature > 1:
            raise ValueError("Temperature must be between 0 and 1.")
        if self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive.")

    @classmethod
    def default(cls, model_name: str = "gemini-2.5-flash") -> AgentConfig:
        return cls(
            model=Model(name=model_name),
            temperature=0.7,
            max_tokens=2048,
        )
