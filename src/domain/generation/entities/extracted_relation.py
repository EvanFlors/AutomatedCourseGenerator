from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from src.domain.shared.exceptions.validation_error import ValidationError


class ExtractedRelation:
    """A raw relation produced by a `RelationClassificationAgent`.

    The endpoints are referenced by the *name* of the source and
    target concepts (not by id), because at the moment the
    classifier runs, the concepts do not yet have stable ids. The
    service layer is responsible for resolving names to ids and
    creating the corresponding `ConceptRelation` instance.
    """

    def __init__(
        self,
        source_name: str,
        target_name: str,
        relation_type: RelationType,
        weight: float = 1.0,
        rationale: str | None = None,
    ):
        self.source_name = source_name.strip() if source_name else ""
        self.target_name = target_name.strip() if target_name else ""
        self.relation_type = relation_type
        self.weight = weight
        self.rationale = rationale.strip() if rationale else None
        self._validate()

    def _validate(self) -> None:
        if not self.source_name:
            raise ValidationError("ExtractedRelation source_name cannot be empty.")
        if not self.target_name:
            raise ValidationError("ExtractedRelation target_name cannot be empty.")
        if self.source_name.lower() == self.target_name.lower():
            raise ValidationError(
                "ExtractedRelation source and target must differ."
            )
        if not isinstance(self.relation_type, RelationType):
            raise ValidationError(
                f"relation_type must be a RelationType, got {type(self.relation_type).__name__}."
            )
        if self.weight < 0:
            raise ValidationError("ExtractedRelation weight cannot be negative.")

    def __repr__(self) -> str:
        return (
            f"ExtractedRelation({self.source_name!r} "
            f"--{self.relation_type.name}--> {self.target_name!r})"
        )
