from src.domain.shared.exceptions.validation_error import ValidationError


class ExtractedConcept:
    """A raw concept produced by a `ConceptExtractionAgent`.

    Unlike `Concept` (the persisted graph node), `ExtractedConcept`
    is a transient DTO that the LLM emits. The service layer is
    responsible for assigning stable ids and any embeddings before
    these become `Concept` instances in the graph.
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
        confidence: float = 1.0,
    ):
        self.name = name.strip() if name else ""
        self.description = description.strip() if description else None
        self.confidence = confidence
        self._validate()

    def _validate(self) -> None:
        if not self.name:
            raise ValidationError("ExtractedConcept name cannot be empty.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError(
                f"confidence must be in [0, 1], got {self.confidence}."
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExtractedConcept):
            return NotImplemented
        return self.name.lower() == other.name.lower()

    def __hash__(self) -> int:
        return hash(self.name.lower())

    def __repr__(self) -> str:
        return f"ExtractedConcept(name={self.name!r})"
