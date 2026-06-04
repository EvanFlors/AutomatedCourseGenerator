import pytest

from src.domain.generation.entities.extracted_concept import ExtractedConcept
from src.domain.generation.entities.extracted_relation import ExtractedRelation
from src.domain.generation.entities.extraction_result import ExtractionResult
from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from src.domain.shared.exceptions.validation_error import ValidationError


class TestExtractionResultValidation:
    def test_empty_result_is_valid(self):
        result = ExtractionResult()

        assert result.is_empty()
        assert result.concepts == []
        assert result.relations == []

    def test_concepts_only_is_valid(self):
        result = ExtractionResult(
            concepts=[ExtractedConcept(name="A"), ExtractedConcept(name="B")]
        )

        assert not result.is_empty()
        assert len(result.concepts) == 2

    def test_relation_with_unknown_endpoint_rejected(self):
        with pytest.raises(ValidationError, match="unknown concept"):
            ExtractionResult(
                concepts=[ExtractedConcept(name="A")],
                relations=[ExtractedRelation(
                    source_name="A",
                    target_name="B",
                    relation_type=RelationType.RELATED_TO,
                )],
            )

    def test_relation_with_unknown_source_rejected(self):
        with pytest.raises(ValidationError, match="unknown concept"):
            ExtractionResult(
                concepts=[ExtractedConcept(name="B")],
                relations=[ExtractedRelation(
                    source_name="A",
                    target_name="B",
                    relation_type=RelationType.RELATED_TO,
                )],
            )

    def test_matching_is_case_sensitive(self):
        """The validator checks exact name match, not case-insensitive."""
        with pytest.raises(ValidationError, match="unknown concept"):
            ExtractionResult(
                concepts=[ExtractedConcept(name="Machine Learning")],
                relations=[ExtractedRelation(
                    source_name="machine learning",
                    target_name="x",
                    relation_type=RelationType.RELATED_TO,
                )],
            )


class TestExtractionResultMerge:
    def test_merge_two_empty_results(self):
        a = ExtractionResult()
        b = ExtractionResult()

        merged = a.merge(b)

        assert merged.is_empty()

    def test_merge_concepts_deduplicates_case_insensitive(self):
        a = ExtractionResult(concepts=[ExtractedConcept(name="ML", description="first")])
        b = ExtractionResult(concepts=[ExtractedConcept(name="ml", description="second")])

        merged = a.merge(b)

        assert len(merged.concepts) == 1
        assert merged.concepts[0].description == "first"

    def test_merge_concepts_combines_unique(self):
        a = ExtractionResult(concepts=[ExtractedConcept(name="A")])
        b = ExtractionResult(concepts=[ExtractedConcept(name="B")])

        merged = a.merge(b)

        assert {c.name for c in merged.concepts} == {"A", "B"}

    def test_merge_keeps_relations_with_known_endpoints(self):
        a = ExtractionResult(
            concepts=[ExtractedConcept(name="A"), ExtractedConcept(name="B")],
        )
        b = ExtractionResult(
            concepts=[ExtractedConcept(name="C")],
        )
        rel = ExtractedRelation(
            source_name="A",
            target_name="C",
            relation_type=RelationType.RELATED_TO,
        )
        b.relations.append(rel)

        merged = a.merge(b)

        assert len(merged.concepts) == 3
        assert len(merged.relations) == 1
        assert merged.relations[0].target_name == "C"

    def test_merge_drops_orphan_relations(self):
        a = ExtractionResult(concepts=[ExtractedConcept(name="A")])
        b = ExtractionResult(concepts=[ExtractedConcept(name="B")])
        orphan = ExtractedRelation(
            source_name="X",
            target_name="Y",
            relation_type=RelationType.RELATED_TO,
        )
        a.relations.append(orphan)

        merged = a.merge(b)

        assert merged.relations == []
        assert {c.name for c in merged.concepts} == {"A", "B"}
