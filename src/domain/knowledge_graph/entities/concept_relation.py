from uuid import uuid4

from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from src.domain.shared.exceptions.validation_error import ValidationError


class ConceptRelation:
    """A directed, typed edge between two concepts in the knowledge graph.

    The relation always has a source and a target concept, a type, and
    an optional weight (used to rank or filter during retrieval) and
    metadata (provenance, confidence score, etc.).
    """

    def __init__(
        self,
        source_concept_id: str,
        target_concept_id: str,
        relation_type: RelationType,
        weight: float = 1.0,
        metadata: dict | None = None,
        id: str | None = None,
    ):

        self.id = id or str(uuid4())

        self.source_concept_id = source_concept_id
        self.target_concept_id = target_concept_id
        self.relation_type = relation_type
        self.weight = weight
        self.metadata = dict(metadata) if metadata else {}

        self._validate()

    def _validate(self):

        if not self.source_concept_id:
            raise ValidationError("Source concept id cannot be empty.")

        if not self.target_concept_id:
            raise ValidationError("Target concept id cannot be empty.")

        if self.source_concept_id == self.target_concept_id:
            raise ValidationError(
                "Source and target concept ids must be different."
            )

        if not isinstance(self.relation_type, RelationType):
            raise ValidationError(
                f"relation_type must be a RelationType, got {type(self.relation_type).__name__}."
            )

        if self.weight < 0:
            raise ValidationError("Relation weight cannot be negative.")

    def set_weight(self, weight: float) -> None:
        if weight < 0:
            raise ValidationError("Relation weight cannot be negative.")
        self.weight = weight

    def update_metadata(self, metadata: dict) -> None:
        if not isinstance(metadata, dict):
            raise ValidationError("Metadata must be a dictionary.")
        self.metadata = dict(metadata)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConceptRelation):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f"ConceptRelation("
            f"source={self.source_concept_id[:8]}, "
            f"target={self.target_concept_id[:8]}, "
            f"type={self.relation_type.name}"
            f")"
        )
