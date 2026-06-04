from abc import ABC, abstractmethod


class EmbeddingService(ABC):
    """Port for generating vector embeddings of text.

    Implementations call a model (e.g. Gemini's
    `text-embedding-004` or OpenAI's `text-embedding-3-small`) and
    return a fixed-length `list[float]`. The dimensionality is
    implementation-defined but should be documented in the
    concrete adapter.
    """

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return the embedding vector for `text`."""

    @abstractmethod
    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for many texts in a single batch call."""
