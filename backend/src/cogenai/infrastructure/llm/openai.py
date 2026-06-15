import os

from cogenai.domain.value_objects.llm import CompletionRequest, CompletionResponse, CompletionUsage
from cogenai.infrastructure.llm.base import BaseLLMAdapter


class OpenAIAdapter(BaseLLMAdapter):

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self._api_key:
            raise ValueError("OpenAI API key must be provided")

    def _call_provider(self, request: CompletionRequest) -> CompletionResponse:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI library is not installed. Please install it with 'pip install openai'")  # noqa: B904

        client = OpenAI(api_key=self._api_key)

        messages = []

        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt}
            )
            messages.append({
                "role": "user",
                "content": request.prompt
            })

        response = client.chat.completions.create(
            model=request.model.name,
            messages=messages,
            temperature=request.model.temperature,
            max_tokens=request.model.max_tokens,
            top_p=request.model.top_p,
            stop=request.stop_sequences,
        )

        choice = response.choices[0]
        usage = response.usage

        return CompletionResponse(
            text=choice.message.content or "",
            model=request.model,
            usage=CompletionUsage(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            ),
            finish_reason=choice.finish_reason or "stop",
        )
