import pytest

from src.domain.generation.entities.extracted_relation import ExtractedRelation
from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from src.domain.shared.exceptions.validation_error import ValidationError


class TestExtractedRelation:
    def test_creates_with_minimum_fields(self):
        r = ExtractedRelation(
            source_name="Supervised Learning",
            target_name="Linear Regression",
            relation_type=RelationType.PREREQUISITE_OF,
        )

        assert r.source_name == "Supervised Learning"
        assert r.target_name == "Linear Regression"
        assert r.relation_type == RelationType.PREREQUISITE_OF
        assert r.weight == 1.0
        assert r.rationale is None

    def test_creates_with_all_fields(self):
        r = ExtractedRelation(
            source_name="A",
            target_name="B",
            relation_type=RelationType.RELATED_TO,
            weight=0.7,
            rationale="Both discuss classification.",
        )

        assert r.weight == 0.7
        assert r.rationale == "Both discuss classification."

    def test_strips_whitespace(self):
        r = ExtractedRelation(
            source_name="  A  ",
            target_name="  B  ",
            relation_type=RelationType.RELATED_TO,
            rationale="  because  ",
        )

        assert r.source_name == "A"
        assert r.target_name == "B"
        assert r.rationale == "because"

    def test_rejects_empty_source(self):
        with pytest.raises(ValidationError, match="source_name"):
            ExtractedRelation(
                source_name="",
                target_name="B",
                relation_type=RelationType.RELATED_TO,
            )

    def test_rejects_empty_target(self):
        with pytest.raises(ValidationError, match="target_name"):
            ExtractedRelation(
                source_name="A",
                target_name="",
                relation_type=RelationType.RELATED_TO,
            )

    def test_rejects_self_loop_case_sensitive(self):
        with pytest.raises(ValidationError, match="must differ"):
            ExtractedRelation(
                source_name="ML",
                target_name="ML",
                relation_type=RelationType.RELATED_TO,
            )

    def test_rejects_self_loop_case_insensitive(self):
        with pytest.raises(ValidationError, match="must differ"):
            ExtractedRelation(
                source_name="ML",
                target_name="ml",
                relation_type=RelationType.RELATED_TO,
            )

    def test_rejects_negative_weight(self):
        with pytest.raises(ValidationError, match="weight cannot be negative"):
            ExtractedRelation(
                source_name="A",
                target_name="B",
                relation_type=RelationType.RELATED_TO,
                weight=-0.1,
            )

    def test_rejects_invalid_relation_type(self):
        with pytest.raises(ValidationError, match="relation_type must be"):
            ExtractedRelation(
                source_name="A",
                target_name="B",
                relation_type="RELATED_TO",
            )

    @pytest.mark.parametrize(
        "rt",
        [RelationType.BELONGS_TO, RelationType.PREREQUISITE_OF,
         RelationType.RELATED_TO, RelationType.EXTENDS],
    )
    def test_all_relation_types_accepted(self, rt):
        r = ExtractedRelation(
            source_name="A", target_name="B", relation_type=rt,
        )

        assert r.relation_type == rt
