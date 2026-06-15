from abc import ABC, abstractmethod

from cogenai.domain.ports.llm import LLMProvider
from cogenai.domain.value_objects.llm import (
    CompletionRequest,
    CompletionResponse,
)


class BaseLLMAdapter(LLMProvider, ABC):

    @abstractmethod
    def _call_provider(self, request: CompletionRequest) -> CompletionResponse:
        ...


    def complete(self, request: CompletionRequest) -> CompletionResponse:
        return self._call_provider(request)
