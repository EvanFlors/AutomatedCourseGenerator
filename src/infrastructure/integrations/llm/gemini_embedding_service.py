"""Embedding service adapters.

`GeminiEmbeddingService` calls the `text-embedding-004` model
via the `google-genai` SDK. The MVP dimensionality is 768
(Gemini's default for `text-embedding-004`); the Neo4j vector
index is configured to match.
"""
from __future__ import annotations

import asyncio

from src.domain.generation.repositories.embedding_service import EmbeddingService
from src.domain.shared.exceptions.validation_error import ValidationError


class GeminiEmbeddingService(EmbeddingService):
    """Embedding service backed by Gemini `text-embedding-004`.

    The output dimensionality is 768; update
    `vector.dimensions` in `_ensure_schema` if you switch models.
    """

    DIMENSIONS = 768

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-004",
        max_batch_size: int = 100,
    ):
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "google-genai is required for GeminiEmbeddingService."
            ) from exc
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_batch_size = max_batch_size

    async def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValidationError("Cannot embed empty text.")
        result = await self._client.aio.models.embed_content(
            model=self._model,
            contents=text,
        )
        return list(result.embeddings[0].values)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batches = [
            texts[i : i + self._max_batch_size]
            for i in range(0, len(texts), self._max_batch_size)
        ]
        batch_results = await asyncio.gather(
            *(self._embed_batch(b) for b in batches)
        )
        vectors: list[list[float]] = []
        for batch in batch_results:
            vectors.extend(batch)
        return vectors

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        result = await self._client.aio.models.embed_content(
            model=self._model,
            contents=batch,
        )
        return [list(e.values) for e in result.embeddings]


class FakeEmbeddingService(EmbeddingService):
    """Deterministic embedding service for tests.

    Embeddings are tiny 4-dimensional vectors derived from a hash
    of the text. The same input always produces the same vector,
    so cosine similarity tests are reproducible.
    """

    DIMENSIONS = 4

    async def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValidationError("Cannot embed empty text.")
        return self._vector_for(text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        digest = sum(ord(c) for c in text)
        return [
            (digest * 1) % 97 / 97.0,
            (digest * 2) % 89 / 89.0,
            (digest * 3) % 83 / 83.0,
            (digest * 5) % 79 / 79.0,
        ]
