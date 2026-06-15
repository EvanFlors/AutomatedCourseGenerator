import os

from cogenai.domain.value_objects.llm import CompletionRequest, CompletionResponse, CompletionUsage
from cogenai.infrastructure.llm.base import BaseLLMAdapter


class GeminiAdapter(BaseLLMAdapter):

    def __init__(self,
        api_key: str | None = None,
        use_credentials: bool = False,
        location: str | None = None,
        scope: str | None = None
    ):
        self._api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self._use_credentials = use_credentials
        self._location = location
        self._scope = scope

        if not self._use_credentials and not self._api_key:
            raise ValueError("Google API key must be provided")

    def _call_provider(self, request: CompletionRequest) -> CompletionResponse:
        try:
            from google import genai
            from google.auth import default
            from google.genai.types import Content, Part
        except ImportError:
            raise ImportError("Google GenAI library is not installed. Please install it with 'pip install google-genai'")  # noqa: B904

        if self._use_credentials:
            if not self._scope:
                raise ValueError("Google API scope must be provided when using credentials")
            if not self._location:
                raise ValueError("Google API location must be provided when using credentials")
            credentials, project_id = default()
            client = genai.Client(
                vertexai=True,
                project=project_id,
                location=self._location,
                credentials=credentials,
            )
        else:
            client = genai.Client(self._api_key)

        contents: list[Content] = []

        if request.system_prompt:
            contents.append(Content(role="model", parts=[Part(text=request.system_prompt)]))

        contents.append(Content(role="user", parts=[Part(text=request.prompt)]))

        config = {
            "temperature": request.model.temperature,
            "max_output_tokens": request.model.max_tokens,
            "top_p": request.model.top_p,
            "stop_sequences": request.stop_sequences,
        }

        if request.output_schema:
            config["response_schema"] = request.output_schema
            config["response_mime_type"] = "application/json"

        response = client.models.generate_content(
            model=request.model.name,
            contents=contents,
            config=config,
        )

        text = response.text or ""

        usage = getattr(response, "usage_metadata", None)

        return CompletionResponse(
            text=text,
            model=request.model,
            usage=CompletionUsage(
                input_tokens=getattr(usage, "prompt_token_count", 0),
                output_tokens=getattr(usage, "candidates_token_count", 0),
                total_tokens=getattr(usage, "total_token_count", 0),
            ),
            finish_reason="stop",
        )
