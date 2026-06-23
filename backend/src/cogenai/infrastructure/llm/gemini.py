import os

from cogenai.domain.value_objects.llm import CompletionRequest, CompletionResponse, CompletionUsage
from cogenai.infrastructure.llm.base import BaseLLMAdapter
from cogenai.infrastructure.llm.factory import LLMClientFactory


class GeminiAdapter(BaseLLMAdapter):

    _client = None
    JSON_MIME_TYPE = "application/json"

    def __init__(
        self,
        **kwargs
    ):
        self._load_dependencies()
        self.client = LLMClientFactory.gemini(**kwargs)

    def _call_provider(
        self,
        request: CompletionRequest,
    ) -> CompletionResponse:

        response = self.client.models.generate_content(
            model=request.model.name,
            contents=self._build_contents(request),
            config=self._build_generation_config(request),
        )

        return CompletionResponse(
            text=response.text or "",
            model=request.model,
            usage=self._build_usage(response),
            finish_reason="stop",
        )

    def health_check(self) -> bool:
        try:
            next(iter(self.client.models.list()))
            return True
        except Exception:
            return False

    def _load_dependencies(self):
        try:
            from google import genai
            from google.auth import default
            from google.genai.types import Content, Part

            self._genai = genai
            self._google_default = default
            self._Content = Content
            self._Part = Part

        except ImportError as exc:
            raise ImportError(
                "Install google-genai: pip install google-genai"
            ) from exc

    def _build_contents(
        self,
        request: CompletionRequest,
    ) -> list:
        contents = []

        if request.system_prompt:
            contents.append(
                self._Content(
                    role="model",
                    parts=[
                        self._Part(
                            text=request.system_prompt
                        )
                    ],
                )
            )

        contents.append(
            self._Content(
                role="user",
                parts=[
                    self._Part(
                        text=request.prompt
                    )
                ],
            )
        )

        return contents

    def _build_generation_config(
        self,
        request: CompletionRequest,
    ) -> dict:
        config = {
            "temperature": request.model.temperature,
            "max_output_tokens": request.model.max_tokens,
            "top_p": request.model.top_p,
            "stop_sequences": request.stop_sequences,
        }

        if request.output_schema:
            config.update(
                {
                    "response_schema": request.output_schema,
                    "response_mime_type": self.JSON_MIME_TYPE,
                }
            )

        return config

    @staticmethod
    def _build_usage(response) -> CompletionUsage:
        usage = getattr(response, "usage_metadata", None)

        return CompletionUsage(
            input_tokens=getattr(
                usage,
                "prompt_token_count",
                0,
            ),
            output_tokens=getattr(
                usage,
                "candidates_token_count",
                0,
            ),
            total_tokens=getattr(
                usage,
                "total_token_count",
                0,
            ),
        )