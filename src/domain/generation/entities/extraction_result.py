from src.domain.generation.entities.extracted_concept import ExtractedConcept
from src.domain.generation.entities.extracted_relation import ExtractedRelation
from src.domain.shared.exceptions.validation_error import ValidationError


class ExtractionResult:
    """The concepts and relations extracted from a single text chunk.

    `ExtractionResult` is what each pipeline stage (concept
    extraction, relation classification) returns. The
    `CourseGenerationService` aggregates the results of many
    chunks into a final knowledge graph.
    """

    def __init__(
        self,
        concepts: list[ExtractedConcept] | None = None,
        relations: list[ExtractedRelation] | None = None,
    ):
        self.concepts = list(concepts or [])
        self.relations = list(relations or [])
        self._validate()

    def _validate(self) -> None:
        seen_names = {c.name.lower() for c in self.concepts}
        for rel in self.relations:
            src = rel.source_name.lower()
            tgt = rel.target_name.lower()
            if src not in seen_names or tgt not in seen_names:
                raise ValidationError(
                    f"ExtractionResult relation references unknown concept: "
                    f"{rel.source_name!r} -> {rel.target_name!r}. "
                    "Both endpoints must be present in `concepts`."
                )

    def is_empty(self) -> bool:
        return not self.concepts and not self.relations

    def merge(self, other: "ExtractionResult") -> "ExtractionResult":
        """Return a new result that combines `self` and `other`.

        Concepts are deduplicated by lowercased name (keeping the
        first occurrence). Relations whose endpoints are not in
        the merged concept set are dropped (this allows merging
        results from chunks that referenced concepts that exist
        in a different chunk).
        """
        merged_concepts: dict[str, ExtractedConcept] = {
            c.name.lower(): c for c in self.concepts
        }
        for c in other.concepts:
            merged_concepts.setdefault(c.name.lower(), c)

        valid_names = set(merged_concepts.keys())
        all_relations = list(self.relations) + list(other.relations)
        kept_relations = [
            r
            for r in all_relations
            if r.source_name.lower() in valid_names
            and r.target_name.lower() in valid_names
        ]
        return ExtractionResult._unsafe(
            concepts=list(merged_concepts.values()),
            relations=kept_relations,
        )

    @classmethod
    def _unsafe(
        cls,
        *,
        concepts: list[ExtractedConcept],
        relations: list[ExtractedRelation],
    ) -> "ExtractionResult":
        """Build an instance without re-validating.

        Used by `merge` to skip the strict constructor check,
        since the input components were already validated.
        """
        instance = cls.__new__(cls)
        instance.concepts = list(concepts)
        instance.relations = list(relations)
        return instance

    def __repr__(self) -> str:
        return (
            f"ExtractionResult(concepts={len(self.concepts)}, "
            f"relations={len(self.relations)})"
        )
