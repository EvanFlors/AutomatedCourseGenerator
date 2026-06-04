import pytest

from src.domain.knowledge_graph.entities.concept import Concept
from src.domain.shared.exceptions.validation_error import ValidationError


class TestConceptInstantiation:
    def test_creates_concept_with_minimal_data(self):
        concept = Concept(name="Machine Learning")

        assert concept.id is not None
        assert concept.name == "Machine Learning"
        assert concept.description is None
        assert concept.embedding is None
        assert concept.source_topic_id is None
        assert concept.source_course_id is None
        assert concept.metadata == {}

    def test_strips_whitespace_from_name(self):
        concept = Concept(name="  Padded  ")

        assert concept.name == "Padded"

    def test_strips_whitespace_from_description(self):
        concept = Concept(name="X", description="  desc  ")

        assert concept.description == "desc"

    def test_treats_empty_description_as_none(self):
        concept = Concept(name="X", description="")

        assert concept.description is None

    def test_copies_metadata_dict(self):
        original = {"source": "video-1"}
        concept = Concept(name="X", metadata=original)

        original["source"] = "video-2"

        assert concept.metadata == {"source": "video-1"}

    def test_copies_embedding_list(self):
        original = [0.1, 0.2, 0.3]
        concept = Concept(name="X", embedding=original)

        original.append(0.4)

        assert concept.embedding == [0.1, 0.2, 0.3]

    def test_generates_uuid_id_when_not_provided(self):
        concept = Concept(name="X")

        assert isinstance(concept.id, str)
        assert len(concept.id) == 36

    def test_preserves_provided_id(self):
        concept = Concept(name="X", id="custom-id")

        assert concept.id == "custom-id"

    def test_accepts_embedding(self):
        concept = Concept(name="X", embedding=[0.1] * 768)

        assert concept.embedding is not None
        assert len(concept.embedding) == 768

    def test_accepts_source_refs(self):
        concept = Concept(
            name="X",
            source_topic_id="t-1",
            source_course_id="c-1",
        )

        assert concept.source_topic_id == "t-1"
        assert concept.source_course_id == "c-1"


class TestConceptValidation:
    def test_raises_validation_error_on_empty_name(self):
        with pytest.raises(ValidationError, match="name cannot be empty"):
            Concept(name="")

    def test_raises_validation_error_on_whitespace_name(self):
        with pytest.raises(ValidationError, match="name cannot be empty"):
            Concept(name="   ")

    def test_raises_validation_error_on_empty_embedding_list(self):
        with pytest.raises(ValidationError, match="embedding cannot be an empty"):
            Concept(name="X", embedding=[])


class TestConceptUpdateMethods:
    def test_update_description_replaces_value(self):
        concept = Concept(name="X", description="old")

        concept.update_description("new")

        assert concept.description == "new"

    def test_update_description_to_none(self):
        concept = Concept(name="X", description="old")

        concept.update_description(None)

        assert concept.description is None

    def test_update_description_strips_whitespace(self):
        concept = Concept(name="X")

        concept.update_description("  desc  ")

        assert concept.description == "desc"

    def test_set_embedding_replaces_value(self):
        concept = Concept(name="X")

        concept.set_embedding([0.1, 0.2])

        assert concept.embedding == [0.1, 0.2]

    def test_set_embedding_to_none(self):
        concept = Concept(name="X", embedding=[0.1])

        concept.set_embedding(None)

        assert concept.embedding is None

    def test_set_embedding_rejects_empty_list(self):
        concept = Concept(name="X")

        with pytest.raises(ValidationError, match="embedding cannot be an empty"):
            concept.set_embedding([])

        assert concept.embedding is None

    def test_set_embedding_copies_list(self):
        concept = Concept(name="X")
        original = [0.1, 0.2]

        concept.set_embedding(original)
        original.append(0.3)

        assert concept.embedding == [0.1, 0.2]

    def test_update_metadata_replaces_dict(self):
        concept = Concept(name="X", metadata={"a": 1})

        concept.update_metadata({"b": 2})

        assert concept.metadata == {"b": 2}

    def test_update_metadata_copies_dict(self):
        concept = Concept(name="X")
        original = {"a": 1}

        concept.update_metadata(original)
        original["a"] = 99

        assert concept.metadata == {"a": 1}

    def test_update_metadata_rejects_non_dict(self):
        concept = Concept(name="X")

        with pytest.raises(ValidationError, match="Metadata must be a dictionary"):
            concept.update_metadata("not a dict")


class TestConceptEquality:
    def test_concepts_with_same_id_are_equal(self):
        a = Concept(name="X", id="same-id")
        b = Concept(name="Y", id="same-id")

        assert a == b

    def test_concepts_with_different_ids_are_not_equal(self):
        a = Concept(name="X")
        b = Concept(name="X")

        assert a != b

    def test_concept_not_equal_to_non_concept(self):
        concept = Concept(name="X")

        assert concept != "X"
        assert concept != 42
        assert concept != None  # noqa: E711

    def test_concepts_can_be_used_in_sets(self):
        a = Concept(name="X", id="id-1")
        b = Concept(name="Y", id="id-1")
        c = Concept(name="Z", id="id-3")

        s = {a, b, c}

        assert len(s) == 2

    def test_repr_includes_id_and_name(self):
        concept = Concept(name="ML", id="abc")

        r = repr(concept)

        assert "abc" in r
        assert "ML" in r
