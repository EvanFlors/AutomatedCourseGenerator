from abc import ABC, abstractmethod

from src.domain.generation.entities.extraction_result import ExtractionResult
from src.domain.generation.repositories.chunking_service import TextChunk


class ConceptExtractionAgent(ABC):
    """Port for the first LLM pass: extract concepts from a chunk.

    Implementations are expected to call an LLM (e.g. Gemini) with
    a structured prompt and parse the JSON response into
    `ExtractionResult`. They should be deterministic given a
    pinned model and temperature.
    """

    @abstractmethod
    async def extract_from_chunk(self, chunk: TextChunk) -> ExtractionResult:
        """Return the concepts (without relations) extracted from `chunk`."""
