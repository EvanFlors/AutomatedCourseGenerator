import pytest

from src.domain.generation.entities.course_source import CourseSource
from src.domain.generation.value_objects.source_type import SourceType
from src.domain.shared.exceptions.validation_error import ValidationError


class TestTextSource:
    def test_creates_with_content(self):
        source = CourseSource(source_type=SourceType.TEXT, content="hello")

        assert source.source_type == SourceType.TEXT
        assert source.content == "hello"
        assert source.url is None
        assert source.extracted_text is None

    def test_rejects_empty_content(self):
        with pytest.raises(ValidationError, match="TEXT source requires"):
            CourseSource(source_type=SourceType.TEXT, content="")

    def test_rejects_whitespace_only_content(self):
        with pytest.raises(ValidationError, match="TEXT source requires"):
            CourseSource(source_type=SourceType.TEXT, content="   \n\t")

    def test_rejects_missing_content(self):
        with pytest.raises(ValidationError, match="TEXT source requires"):
            CourseSource(source_type=SourceType.TEXT, content=None)

    def test_rejects_invalid_source_type(self):
        with pytest.raises(ValidationError, match="source_type must be a SourceType"):
            CourseSource(source_type="text", content="hello")


class TestUrlSource:
    def test_creates_with_url(self):
        source = CourseSource(source_type=SourceType.URL, url="https://example.com")

        assert source.source_type == SourceType.URL
        assert source.url == "https://example.com"
        assert source.content is None

    def test_rejects_empty_url(self):
        with pytest.raises(ValidationError, match="URL source requires"):
            CourseSource(source_type=SourceType.URL, url="")

    def test_rejects_whitespace_url(self):
        with pytest.raises(ValidationError, match="URL source requires"):
            CourseSource(source_type=SourceType.URL, url="   ")


class TestUnsupportedTypes:
    def test_rejects_youtube_in_mvp(self):
        with pytest.raises(ValidationError, match="not supported"):
            CourseSource(source_type=SourceType.YOUTUBE, url="https://youtu.be/x")

    def test_rejects_pdf_in_mvp(self):
        with pytest.raises(ValidationError, match="not supported"):
            CourseSource(source_type=SourceType.PDF, url="file://x.pdf")


class TestExtractedText:
    def test_set_extracted_text_strips_and_stores(self):
        source = CourseSource(source_type=SourceType.TEXT, content="raw")

        source.set_extracted_text("  cleaned  \n")

        assert source.extracted_text == "cleaned"

    def test_set_extracted_text_rejects_empty(self):
        source = CourseSource(source_type=SourceType.TEXT, content="x")

        with pytest.raises(ValidationError, match="Extracted text cannot be empty"):
            source.set_extracted_text("   ")


class TestEffectiveText:
    def test_prefers_extracted_text(self):
        source = CourseSource(source_type=SourceType.TEXT, content="raw")
        source.set_extracted_text("cleaned")

        assert source.effective_text == "cleaned"

    def test_falls_back_to_content(self):
        source = CourseSource(source_type=SourceType.TEXT, content="raw only")

        assert source.effective_text == "raw only"

    def test_returns_empty_when_neither_set(self):
        source = CourseSource(source_type=SourceType.URL, url="https://x")

        assert source.effective_text == ""
