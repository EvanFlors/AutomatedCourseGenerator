from cogenai.domain.value_objects.llm import CompletionRequest, CompletionResponse, CompletionUsage
from cogenai.infrastructure.llm.base import BaseLLMAdapter


class StubAdapter(BaseLLMAdapter):

    def __init__(self, response_text: str = "This is a stub response."):
        self._response_text = response_text

    def _call_provider(self, request: CompletionRequest) -> CompletionResponse:

        prompt_length = len(request.prompt)
        output_length = len(self._response_text)

        return CompletionResponse(
            text=self._response_text,
            model=request.model,
            usage=CompletionUsage(
                input_tokens=prompt_length // 4,
                output_tokens=output_length // 4,
                total_tokens=(prompt_length + output_length) // 4,
            ),
            finish_reason="stop",
        )
