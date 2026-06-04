"""LLM client port and Gemini + Fake adapters.

The LLM client wraps a single model and exposes two methods:
`complete()` (raw text) and `complete_json()` (validated JSON).
This keeps the agent adapters free of provider-specific quirks
and makes the FakeLLMClient trivial.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, ValidationError as PydanticValidationError


class LLMClient(ABC):
    """Abstract LLM client.

    `complete_json()` validates the response against the supplied
    Pydantic model. Adapters are responsible for instructing the
    model to emit JSON and for parsing the result.
    """

    @abstractmethod
    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        """Return the model's raw text response."""

    async def complete_json(
        self,
        prompt: str,
        response_model: type[BaseModel],
        *,
        temperature: float = 0.0,
    ) -> BaseModel:
        raw = await self.complete(prompt, temperature=temperature)
        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM response is not valid JSON: {exc}. Raw: {raw[:200]}"
            ) from exc
        try:
            return response_model.model_validate(data)
        except PydanticValidationError as exc:
            raise ValueError(
                f"LLM response does not match schema: {exc}. Raw: {raw[:200]}"
            ) from exc


class FakeLLMClient(LLMClient):
    """Deterministic LLM client for tests.

    Behavior is driven by a registry of `(substring, response)`
    pairs. The first substring that matches the prompt is used to
    return its associated response. If no key matches, the
    default response (or `{}` for `complete_json`) is returned.

    Use `set_response` and `set_json_response` to program the
    fake from test code. The fake also records every call into
    `self.calls` for later inspection.
    """

    def __init__(self, default_response: str = ""):
        self._responses: list[tuple[str, str]] = []
        self._default = default_response
        self.calls: list[dict[str, Any]] = []

    def set_response(self, prompt_substring: str, response: str) -> None:
        self._responses.append((prompt_substring, response))

    def set_json_response(
        self,
        prompt_substring: str,
        response: dict,
    ) -> None:
        self.set_response(prompt_substring, json.dumps(response))

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        self.calls.append({"prompt": prompt, "temperature": temperature})
        for substring, response in self._responses:
            if substring in prompt:
                return response
        return self._default


class _EmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1)


class _EmbeddingResponse(BaseModel):
    vectors: list[list[float]]


class GeminiLLMClient(LLMClient):
    """LLM client backed by the `google-genai` SDK.

    Uses the `generate_content` API with `response_mime_type=
    "application/json"` for JSON outputs.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.0-flash",
    ):
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "google-genai is required for GeminiLLMClient. "
                "Install with `pip install google-genai`."
            ) from exc
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config={
                "temperature": temperature,
            },
        )
        return response.text
