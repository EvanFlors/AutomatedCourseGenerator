from typing import Protocol

from cogenai.domain.value_objects.llm import (
    CompletionRequest,
    CompletionResponse,
)


class LLMProvider(Protocol):

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        ...

    def health_check(self) -> CompletionResponse:
        ...
