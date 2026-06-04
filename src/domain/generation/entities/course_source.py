from src.domain.generation.value_objects.source_type import SourceType
from src.domain.shared.exceptions.validation_error import ValidationError


class CourseSource:
    """A user-provided input to the generation pipeline.

    For TEXT sources, `content` is the raw text already, and `url`
    is None. For URL sources, `url` points to the page to fetch and
    `content` is filled in by the text extraction stage.

    The same `CourseSource` is later enriched with `extracted_text`
    once the text extraction stage has run.
    """

    def __init__(
        self,
        source_type: SourceType,
        content: str | None = None,
        url: str | None = None,
        title: str | None = None,
    ):
        self.source_type = source_type
        self.content = content
        self.url = url
        self.title = title
        self.extracted_text: str | None = None
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.source_type, SourceType):
            raise ValidationError(
                f"source_type must be a SourceType, got {type(self.source_type).__name__}."
            )

        if self.source_type is SourceType.TEXT:
            if not self.content or not self.content.strip():
                raise ValidationError(
                    "TEXT source requires non-empty content."
                )
        elif self.source_type is SourceType.URL:
            if not self.url or not self.url.strip():
                raise ValidationError(
                    "URL source requires a non-empty url."
                )
        else:
            raise ValidationError(
                f"Source type {self.source_type.name} is not supported "
                "in the current generation pipeline MVP."
            )

    def set_extracted_text(self, text: str) -> None:
        if not text or not text.strip():
            raise ValidationError("Extracted text cannot be empty.")
        self.extracted_text = text.strip()

    @property
    def effective_text(self) -> str:
        """Return the text the pipeline should chunk.

        Prefers `extracted_text` (set after the extraction stage)
        over `content` (raw user input). Returns an empty string if
        neither is set.
        """
        return self.extracted_text or self.content or ""

    def __repr__(self) -> str:
        identifier = self.url or (
            f"{len(self.content or '')} chars" if self.content else "empty"
        )
        return f"CourseSource(type={self.source_type.name}, {identifier})"
