from abc import ABC, abstractmethod

from src.domain.generation.entities.course_source import CourseSource


class TextExtractionRepository(ABC):
    """Port for extracting raw text from a `CourseSource`.

    Implementations live in infrastructure. For the MVP:
    * TEXT sources are returned unchanged.
    * URL sources are fetched and parsed (e.g. with trafilatura).
    YOUTUBE and PDF are planned for follow-up sprints.
    """

    @abstractmethod
    async def extract_text(self, source: CourseSource) -> str:
        """Return the raw text of `source`.

        The returned text is the input to the chunking stage. It
        should be plain UTF-8, with no HTML or markdown markup.
        """

    @abstractmethod
    async def extract_many(
        self,
        sources: list[CourseSource],
    ) -> list[CourseSource]:
        """Extract text for many sources in parallel and return them
        with `extracted_text` set.
        """
