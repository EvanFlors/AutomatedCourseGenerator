from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    name: str
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float | None = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Model name cannot be empty.")
        if not (0.0 <= self.temperature <= 1.0):
            raise ValueError("Temperature must be between 0 and 1.")
        if self.max_tokens <= 0:
            raise ValueError("Max tokens must be a positive integer.")
        if self.top_p is not None and not (0.0 <= self.top_p <= 1.0):
            raise ValueError("Top_p must be between 0 and 1 if provided.")

@dataclass(frozen=True)
class CompletionRequest:
    prompt: str
    model: Model
    system_prompt: str | None = None
    stop_sequences: list[str] | None = None
    output_schema: dict | None = None

    def __post_init__(self):
        if not self.prompt:
            raise ValueError("Prompt cannot be empty.")
        if not self.model:
            raise ValueError("Model cannot be empty.")


@dataclass(frozen=True)
class CompletionResponse:
    text: str
    model: Model
    usage: CompletionUsage
    finish_reason: str = "stop"

    def __post_init__(self):
        if not self.text:
            raise ValueError("Text cannot be empty.")
        if not self.model:
            raise ValueError("Model cannot be empty.")
        if not self.usage:
            raise ValueError("Usage cannot be empty.")


@dataclass(frozen=True)
class CompletionUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

    @property
    def cost(self) -> float:
        return (self.input_tokens + self.output_tokens) * 0.0001
