from typing import Protocol, runtime_checkable

from cogenai.domain.value_objects.llm import (
    CompletionRequest,
    CompletionResponse,
)


class LLMProvider(Protocol):

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        ...

    def health_check(self) -> CompletionResponse:
        ...


@runtime_checkable
class SupportsCancellation(Protocol):
    """Optional capability: provider supports in-flight cancellation.

    Adapters that wrap a network call (HTTP, gRPC, subprocess) should
    implement this and raise `AgentCancelled` from `complete()` when
    `cancel()` is invoked. In-memory adapters (StubAdapter) may omit it.
    """

    def cancel(self) -> None:
        ...


class AgentCancelled(Exception):
    """Raised by an LLM adapter when its in-flight call is cancelled.

    Caught by the orchestrator and converted into a clean
    JobStatus.ABORTED transition + termination_reason='user_aborted'.
    """