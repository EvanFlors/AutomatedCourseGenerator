"""Simple, deterministic chunker.

Splits long text into overlapping windows of `chunk_size`
characters with `overlap` characters of shared context. The
chunker tries to break on sentence boundaries (`.`, `!`, `?`,
`\n\n`) when possible, falling back to whitespace.

This implementation is intentionally simple: the goal is to give
the LLM coherent windows of text without a complex sentence
tokenizer. For higher-quality chunking, swap this implementation
for a LangChain splitter in a follow-up sprint.
"""
from __future__ import annotations

from src.domain.generation.repositories.chunking_service import (
    ChunkingService,
    TextChunk,
)


class SimpleChunker(ChunkingService):
    """Character-based chunker with sentence-boundary awareness."""

    def __init__(self, *, chunk_size: int = 2000, overlap: int = 200):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError(
                "overlap must be in [0, chunk_size)."
            )
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, text: str, source_index: int = 0) -> list[TextChunk]:
        if not text:
            return []
        if len(text) <= self._chunk_size:
            return [
                TextChunk(
                    text=text,
                    index=0,
                    start_char=0,
                    end_char=len(text),
                    source_index=source_index,
                )
            ]

        chunks: list[TextChunk] = []
        start = 0
        index = 0
        step = self._chunk_size - self._overlap
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            window = text[start:end]
            if end < len(text):
                boundary = self._find_break(window)
                if boundary > self._chunk_size // 2:
                    end = start + boundary
            chunks.append(
                TextChunk(
                    text=text[start:end],
                    index=index,
                    start_char=start,
                    end_char=end,
                    source_index=source_index,
                )
            )
            index += 1
            if end >= len(text):
                break
            start = max(end - self._overlap, start + 1)
            if start >= end:
                start = end
            if len(chunks) > 1 and start <= chunks[-2].start_char:
                start = end
                if start >= len(text):
                    break
        return chunks

    def _find_break(self, window: str) -> int:
        """Return the index of the last sentence boundary in `window`.

        Returns 0 if no boundary is found.
        """
        best = 0
        for marker in ("\n\n", ". ", "! ", "? ", "\n"):
            idx = window.rfind(marker)
            if idx > best:
                best = idx + len(marker)
        return best
