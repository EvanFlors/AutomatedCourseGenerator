"""Text extraction adapters.

The MVP supports two source types:

* TEXT: the user already provided the text, so we just trim it.
* URL: fetch the page with httpx and extract the main text with
  trafilatura.

YOUTUBE and PDF adapters are planned for a follow-up sprint.
"""
from __future__ import annotations

import asyncio

import httpx
import trafilatura

from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.repositories.text_extraction_repository import (
    TextExtractionRepository,
)
from src.domain.shared.exceptions.validation_error import ValidationError


class TextSourceExtractor(TextExtractionRepository):
    """Extractor that handles TEXT and URL sources.

    For TEXT sources, the `content` field is used directly. For
    URL sources, the page is fetched and parsed with trafilatura
    to strip navigation, ads, and boilerplate.
    """

    def __init__(
        self,
        *,
        http_timeout_seconds: float = 20.0,
        max_concurrent_fetches: int = 4,
    ):
        self._http_timeout = http_timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent_fetches)

    async def extract_text(self, source: CourseSource) -> str:
        if source.source_type.value == "text":
            text = (source.content or "").strip()
            if not text:
                raise ValidationError(
                    "TEXT source has no content to extract."
                )
            return text

        if source.source_type.value == "url":
            assert source.url is not None
            return await self._fetch_url(source.url)

        raise ValidationError(
            f"Source type {source.source_type.name} is not supported by "
            "TextSourceExtractor."
        )

    async def extract_many(
        self,
        sources: list[CourseSource],
    ) -> list[CourseSource]:
        async def _extract(source: CourseSource) -> CourseSource:
            text = await self.extract_text(source)
            source.set_extracted_text(text)
            return source

        return list(await asyncio.gather(*(_extract(s) for s in sources)))

    async def _fetch_url(self, url: str) -> str:
        async with self._semaphore:
            async with httpx.AsyncClient(
                timeout=self._http_timeout,
                follow_redirects=True,
                headers={"User-Agent": "CourseAutomation/1.0"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            include_links=False,
            favor_precision=True,
        )
        if not text:
            raise ValidationError(
                f"Could not extract readable text from URL: {url}"
            )
        return text.strip()
