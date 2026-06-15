from functools import lru_cache
from typing import TypeVar
from collections.abc import Callable

from cogenai.domain.ports.llm import LLMProvider
from cogenai.domain.value_objects.llm import Model
from cogenai.infrastructure.llm.base import BaseLLMAdapter
from cogenai.infrastructure.llm.stub import StubAdapter
from cogenai.infrastructure.llm.gemini import GeminiAdapter
from cogenai.infrastructure.llm.openai import OpenAIAdapter
# from cogenai.infrastructure.llm.anthropic import AnthropicAdapter

from cogenai.bootstrap.settings import settings

T = TypeVar("T", bound=LLMProvider)


class Container:

    def __init__(self):
        self._factories: dict[type[T], Callable[[], T]] = {}

    def register(self, interface: type[T], factory: Callable[[], T]) -> None:
        self._factories[interface] = factory

    def resolve(self, interface: type[T]) -> T:
        if interface not in self._factories:
            raise ValueError(f"No factory registered for {interface}")
        return self._factories[interface]()

# Global container
_container = Container()


def get_llm_provider() -> LLMProvider:

    model = Model(
        name=settings.model,
        temperature=settings.default_temperature,
        max_tokens=settings.default_max_tokens,
    )

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return OpenAIAdapter(api_key=settings.openai_api_key)
    elif settings.llm_provider == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        return GeminiAdapter(api_key=settings.google_api_key)
    elif settings.llm_provider == "stub":
        return StubAdapter(response_text="This is a stub response.")
    else:
        raise ValueError(f"Unknown provider: {settings.llm_provider}")

# Register the default factory
_container.register(LLMProvider, get_llm_provider)

def get_container() -> Container:
    return _container