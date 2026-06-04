import pytest

from src.domain.course.enums.block_type import BlockType


class TestBlockTypeValues:
    def test_all_block_types_defined(self):
        expected = {"HEADING", "TEXT", "CODE", "IMAGE", "QUOTE", "DIVIDER"}
        actual = {member.name for member in BlockType}

        assert actual == expected

    def test_block_type_values_are_lowercase_strings(self):
        for member in BlockType:
            assert member.value == member.value.lower()
            assert isinstance(member.value, str)

    @pytest.mark.parametrize(
        "name,value",
        [
            ("HEADING", "heading"),
            ("TEXT", "text"),
            ("CODE", "code"),
            ("IMAGE", "image"),
            ("QUOTE", "quote"),
            ("DIVIDER", "divider"),
        ],
    )
    def test_block_type_specific_values(self, name, value):
        assert BlockType[name].value == value

    def test_block_type_is_str_subclass(self):
        assert issubclass(BlockType, str)

    def test_block_type_supports_string_comparison(self):
        assert BlockType.TEXT == "text"
        assert BlockType.HEADING == "heading"
