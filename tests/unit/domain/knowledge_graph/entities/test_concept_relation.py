import pytest

from src.domain.knowledge_graph.entities.concept_relation import ConceptRelation
from src.domain.knowledge_graph.value_objects.relation_type import RelationType
from src.domain.shared.exceptions.validation_error import ValidationError


class TestConceptRelationInstantiation:
    def test_creates_relation_with_required_data(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.PREREQUISITE_OF,
        )

        assert rel.id is not None
        assert rel.source_concept_id == "a"
        assert rel.target_concept_id == "b"
        assert rel.relation_type == RelationType.PREREQUISITE_OF
        assert rel.weight == 1.0
        assert rel.metadata == {}

    def test_accepts_custom_weight(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
            weight=0.75,
        )

        assert rel.weight == 0.75

    def test_accepts_metadata(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
            metadata={"confidence": 0.9, "source": "llm"},
        )

        assert rel.metadata == {"confidence": 0.9, "source": "llm"}

    def test_copies_metadata_dict(self):
        original = {"confidence": 0.9}
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
            metadata=original,
        )

        original["confidence"] = 0.1

        assert rel.metadata == {"confidence": 0.9}

    def test_generates_uuid_id_when_not_provided(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
        )

        assert isinstance(rel.id, str)
        assert len(rel.id) == 36

    def test_preserves_provided_id(self):
        rel = ConceptRelation(
            id="custom",
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
        )

        assert rel.id == "custom"

    @pytest.mark.parametrize(
        "relation_type",
        list(RelationType),
    )
    def test_accepts_all_relation_types(self, relation_type):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=relation_type,
        )

        assert rel.relation_type == relation_type


class TestConceptRelationValidation:
    def test_raises_validation_error_on_empty_source_id(self):
        with pytest.raises(ValidationError, match="Source concept id cannot be empty"):
            ConceptRelation(
                source_concept_id="",
                target_concept_id="b",
                relation_type=RelationType.RELATED_TO,
            )

    def test_raises_validation_error_on_empty_target_id(self):
        with pytest.raises(ValidationError, match="Target concept id cannot be empty"):
            ConceptRelation(
                source_concept_id="a",
                target_concept_id="",
                relation_type=RelationType.RELATED_TO,
            )

    def test_raises_validation_error_on_self_loop(self):
        with pytest.raises(ValidationError, match="must be different"):
            ConceptRelation(
                source_concept_id="same",
                target_concept_id="same",
                relation_type=RelationType.RELATED_TO,
            )

    def test_raises_validation_error_on_invalid_relation_type(self):
        with pytest.raises(ValidationError, match="must be a RelationType"):
            ConceptRelation(
                source_concept_id="a",
                target_concept_id="b",
                relation_type="not-a-relation-type",
            )

    def test_raises_validation_error_on_negative_weight(self):
        with pytest.raises(ValidationError, match="weight cannot be negative"):
            ConceptRelation(
                source_concept_id="a",
                target_concept_id="b",
                relation_type=RelationType.RELATED_TO,
                weight=-0.1,
            )

    def test_accepts_zero_weight(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
            weight=0.0,
        )

        assert rel.weight == 0.0


class TestConceptRelationUpdateMethods:
    def test_set_weight_replaces_value(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
            weight=0.5,
        )

        rel.set_weight(0.9)

        assert rel.weight == 0.9

    def test_set_weight_rejects_negative(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
        )

        with pytest.raises(ValidationError, match="weight cannot be negative"):
            rel.set_weight(-0.1)

        assert rel.weight == 1.0

    def test_update_metadata_replaces_dict(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
            metadata={"a": 1},
        )

        rel.update_metadata({"b": 2})

        assert rel.metadata == {"b": 2}

    def test_update_metadata_copies_dict(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
        )
        original = {"x": 1}

        rel.update_metadata(original)
        original["x"] = 99

        assert rel.metadata == {"x": 1}

    def test_update_metadata_rejects_non_dict(self):
        rel = ConceptRelation(
            source_concept_id="a",
            target_concept_id="b",
            relation_type=RelationType.RELATED_TO,
        )

        with pytest.raises(ValidationError, match="Metadata must be a dictionary"):
            rel.update_metadata([1, 2, 3])


class TestConceptRelationEquality:
    def test_relations_with_same_id_are_equal(self):
        a = ConceptRelation(
            id="r1",
            source_concept_id="x",
            target_concept_id="y",
            relation_type=RelationType.RELATED_TO,
        )
        b = ConceptRelation(
            id="r1",
            source_concept_id="other",
            target_concept_id="values",
            relation_type=RelationType.PREREQUISITE_OF,
        )

        assert a == b

    def test_relations_with_different_ids_are_not_equal(self):
        a = ConceptRelation(
            source_concept_id="x",
            target_concept_id="y",
            relation_type=RelationType.RELATED_TO,
        )
        b = ConceptRelation(
            source_concept_id="x",
            target_concept_id="y",
            relation_type=RelationType.RELATED_TO,
        )

        assert a != b

    def test_relation_not_equal_to_non_relation(self):
        rel = ConceptRelation(
            source_concept_id="x",
            target_concept_id="y",
            relation_type=RelationType.RELATED_TO,
        )

        assert rel != "x"
        assert rel != 42

    def test_relations_can_be_used_in_sets(self):
        a = ConceptRelation(
            id="r1",
            source_concept_id="x",
            target_concept_id="y",
            relation_type=RelationType.RELATED_TO,
        )
        b = ConceptRelation(
            id="r1",
            source_concept_id="x",
            target_concept_id="y",
            relation_type=RelationType.RELATED_TO,
        )
        c = ConceptRelation(
            id="r2",
            source_concept_id="x",
            target_concept_id="y",
            relation_type=RelationType.RELATED_TO,
        )

        s = {a, b, c}

        assert len(s) == 2

    def test_repr_contains_type_and_short_ids(self):
        rel = ConceptRelation(
            source_concept_id="abc12345-rest",
            target_concept_id="xyz98765-rest",
            relation_type=RelationType.PREREQUISITE_OF,
        )

        r = repr(rel)

        assert "abc12345" in r
        assert "xyz98765" in r
        assert "PREREQUISITE_OF" in r
