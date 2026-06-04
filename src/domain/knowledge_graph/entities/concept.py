from uuid import uuid4

from src.domain.shared.exceptions.validation_error import ValidationError


class Concept:
    """A knowledge concept extracted from a course's content.

    Concepts are the nodes of the knowledge graph. They can belong to
    one or more topics and be linked to other concepts via
    `ConceptRelation`.
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
        embedding: list[float] | None = None,
        source_topic_id: str | None = None,
        source_course_id: str | None = None,
        metadata: dict | None = None,
        id: str | None = None,
    ):

        self.id = id or str(uuid4())

        self.name = name.strip()

        self.description = (
            description.strip()
            if description
            else None
        )

        self.embedding = (
            list(embedding)
            if embedding is not None
            else None
        )

        self.source_topic_id = source_topic_id
        self.source_course_id = source_course_id

        self.metadata = (
            dict(metadata)
            if metadata
            else {}
        )

        self._validate()

    def _validate(self):

        if not self.name:
            raise ValidationError("Concept name cannot be empty.")

        if self.embedding is not None and not self.embedding:
            raise ValidationError("Concept embedding cannot be an empty list.")

    def update_description(self, description: str | None) -> None:
        self.description = description.strip() if description else None

    def set_embedding(self, embedding: list[float] | None) -> None:
        if embedding is not None and not embedding:
            raise ValidationError("Concept embedding cannot be an empty list.")
        self.embedding = list(embedding) if embedding is not None else None

    def update_metadata(self, metadata: dict) -> None:
        if not isinstance(metadata, dict):
            raise ValidationError("Metadata must be a dictionary.")
        self.metadata = dict(metadata)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Concept):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"Concept(id={self.id!r}, name={self.name!r})"
