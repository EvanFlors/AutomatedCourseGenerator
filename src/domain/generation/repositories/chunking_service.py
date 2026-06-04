from abc import ABC, abstractmethod


class TextChunk:
    """A contiguous slice of a larger text.

    Chunks are the unit of work for the LLM extraction stages. They
    are designed to fit comfortably in a model context window
    (default: ~2000 characters with 200-character overlap).
    """

    def __init__(
        self,
        text: str,
        index: int,
        start_char: int,
        end_char: int,
        source_index: int = 0,
    ):
        self.text = text
        self.index = index
        self.start_char = start_char
        self.end_char = end_char
        self.source_index = source_index

    def __repr__(self) -> str:
        return (
            f"TextChunk(index={self.index}, "
            f"chars={self.start_char}-{self.end_char}, "
            f"len={len(self.text)})"
        )


class ChunkingService(ABC):
    """Port for splitting long text into smaller chunks.

    Implementations should be deterministic and overlap-aware so
    that concepts spanning chunk boundaries are not lost.
    """

    @abstractmethod
    def chunk(self, text: str, source_index: int = 0) -> list[TextChunk]:
        """Split `text` into overlapping chunks.
        """
