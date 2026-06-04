import pytest

from src.domain.knowledge_graph.value_objects.relation_type import RelationType


class TestRelationTypeValues:
    def test_all_relation_types_defined(self):
        expected = {"BELONGS_TO", "PREREQUISITE_OF", "RELATED_TO", "EXTENDS"}
        actual = {member.name for member in RelationType}

        assert actual == expected

    def test_relation_type_values_are_uppercase_strings(self):
        for member in RelationType:
            assert member.value == member.value.upper()
            assert isinstance(member.value, str)

    @pytest.mark.parametrize(
        "name,value",
        [
            ("BELONGS_TO", "BELONGS_TO"),
            ("PREREQUISITE_OF", "PREREQUISITE_OF"),
            ("RELATED_TO", "RELATED_TO"),
            ("EXTENDS", "EXTENDS"),
        ],
    )
    def test_relation_type_specific_values(self, name, value):
        assert RelationType[name].value == value

    def test_relation_type_is_str_subclass(self):
        assert issubclass(RelationType, str)

    def test_relation_type_supports_string_comparison(self):
        assert RelationType.BELONGS_TO == "BELONGS_TO"
        assert RelationType.PREREQUISITE_OF == "PREREQUISITE_OF"

    def test_relation_type_usable_as_cypher_label(self):
        for member in RelationType:
            assert member.value.replace("_", "").isalnum()

    def test_relation_type_count(self):
        assert len(list(RelationType)) == 4
