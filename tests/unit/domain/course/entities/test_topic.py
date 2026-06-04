import pytest

from src.domain.course.entities.content_block import ContentBlock
from src.domain.course.entities.topic import Topic
from src.domain.course.enums.block_type import BlockType
from src.domain.shared.exceptions.validation_error import ValidationError


class TestTopicInstantiation:
    def test_creates_topic_with_minimal_data(self, sample_topic_title):
        topic = Topic(title=sample_topic_title, order=0)

        assert topic.id is not None
        assert topic.title == sample_topic_title
        assert topic.order == 0
        assert topic.blocks == []

    def test_creates_topic_with_blocks(self, sample_block_payload):
        b1 = ContentBlock(block_type=BlockType.TEXT, order=0, payload=sample_block_payload)
        b2 = ContentBlock(block_type=BlockType.HEADING, order=1, payload={"text": "H"})

        topic = Topic(title="T", order=0, blocks=[b1, b2])

        assert topic.blocks == [b1, b2]

    def test_strips_whitespace_from_title(self):
        topic = Topic(title="  Padded  ", order=0)

        assert topic.title == "Padded"

    def test_generates_uuid_id_when_not_provided(self):
        topic = Topic(title="T", order=0)

        assert isinstance(topic.id, str)
        assert len(topic.id) == 36

    def test_preserves_provided_id(self):
        topic = Topic(title="T", order=0, id="custom-id")

        assert topic.id == "custom-id"

    def test_accepts_zero_order(self):
        topic = Topic(title="T", order=0)

        assert topic.order == 0


class TestTopicValidation:
    def test_raises_validation_error_on_empty_title(self):
        with pytest.raises(ValidationError, match="title cannot be empty"):
            Topic(title="", order=0)

    def test_raises_validation_error_on_whitespace_title(self):
        with pytest.raises(ValidationError, match="title cannot be empty"):
            Topic(title="   ", order=0)

    def test_raises_validation_error_on_negative_order(self):
        with pytest.raises(ValidationError, match="order cannot be negative"):
            Topic(title="T", order=-1)


class TestTopicBlockManagement:
    def test_add_block_appends_to_list(self, sample_block_payload):
        topic = Topic(title="T", order=0)
        block = ContentBlock(block_type=BlockType.TEXT, order=0, payload=sample_block_payload)

        topic.add_block(block)

        assert topic.blocks == [block]

    def test_add_block_keeps_blocks_sorted_by_order(self):
        topic = Topic(title="T", order=0)
        b1 = ContentBlock(block_type=BlockType.TEXT, order=2, payload={"text": "1"})
        b2 = ContentBlock(block_type=BlockType.TEXT, order=0, payload={"text": "2"})
        b3 = ContentBlock(block_type=BlockType.TEXT, order=1, payload={"text": "3"})

        topic.add_block(b1)
        topic.add_block(b2)
        topic.add_block(b3)

        assert [b.order for b in topic.blocks] == [0, 1, 2]

    def test_remove_block_filters_by_id(self):
        topic = Topic(title="T", order=0)
        b1 = ContentBlock(block_type=BlockType.TEXT, order=0, payload={"text": "a"})
        b2 = ContentBlock(block_type=BlockType.TEXT, order=1, payload={"text": "b"})
        topic.add_block(b1)
        topic.add_block(b2)

        topic.remove_block(b1.id)

        assert topic.blocks == [b2]

    def test_remove_nonexistent_block_leaves_list_unchanged(self):
        topic = Topic(title="T", order=0)
        b1 = ContentBlock(block_type=BlockType.TEXT, order=0, payload={"text": "a"})
        topic.add_block(b1)

        topic.remove_block("missing-id")

        assert topic.blocks == [b1]

    def test_get_block_returns_matching_block(self):
        topic = Topic(title="T", order=0)
        b1 = ContentBlock(block_type=BlockType.TEXT, order=0, payload={"text": "a"})
        topic.add_block(b1)

        assert topic.get_block(b1.id) is b1

    def test_get_block_returns_none_when_not_found(self):
        topic = Topic(title="T", order=0)

        assert topic.get_block("missing") is None
