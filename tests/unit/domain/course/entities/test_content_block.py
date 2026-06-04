import pytest

from src.domain.course.entities.content_block import ContentBlock
from src.domain.course.enums.block_type import BlockType
from src.domain.shared.exceptions.validation_error import ValidationError


class TestContentBlockInstantiation:
    def test_creates_block_with_text_payload(self, sample_block_payload):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload=sample_block_payload,
        )

        assert block.id is not None
        assert block.type == BlockType.TEXT
        assert block.order == 0
        assert block.payload == sample_block_payload

    @pytest.mark.parametrize(
        "block_type",
        [
            BlockType.HEADING,
            BlockType.TEXT,
            BlockType.CODE,
            BlockType.IMAGE,
            BlockType.QUOTE,
            BlockType.DIVIDER,
        ],
    )
    def test_accepts_all_block_types(self, block_type):
        block = ContentBlock(
            block_type=block_type,
            order=0,
            payload={"text": "x"},
        )

        assert block.type == block_type

    def test_accepts_empty_payload_dict(self):
        block = ContentBlock(
            block_type=BlockType.DIVIDER,
            order=0,
            payload={},
        )

        assert block.payload == {}

    def test_generates_uuid_id_when_not_provided(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "x"},
        )

        assert isinstance(block.id, str)
        assert len(block.id) == 36

    def test_preserves_provided_id(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "x"},
            id="custom-id",
        )

        assert block.id == "custom-id"

    def test_accepts_zero_order(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "x"},
        )

        assert block.order == 0


class TestContentBlockValidation:
    def test_raises_validation_error_on_negative_order(self):
        with pytest.raises(ValidationError, match="order cannot be negative"):
            ContentBlock(
                block_type=BlockType.TEXT,
                order=-1,
                payload={"text": "x"},
            )

    def test_raises_validation_error_on_non_dict_payload(self):
        with pytest.raises(ValidationError, match="Payload must be a dictionary"):
            ContentBlock(
                block_type=BlockType.TEXT,
                order=0,
                payload="not a dict",
            )

    def test_raises_validation_error_on_none_payload(self):
        with pytest.raises(ValidationError, match="Payload must be a dictionary"):
            ContentBlock(
                block_type=BlockType.TEXT,
                order=0,
                payload=None,
            )

    def test_raises_validation_error_on_list_payload(self):
        with pytest.raises(ValidationError, match="Payload must be a dictionary"):
            ContentBlock(
                block_type=BlockType.TEXT,
                order=0,
                payload=[1, 2, 3],
            )


class TestContentBlockUpdatePayload:
    def test_updates_payload_with_valid_dict(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "old"},
        )

        block.update_payload({"text": "new"})

        assert block.payload == {"text": "new"}

    def test_update_payload_raises_on_non_dict(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "old"},
        )

        with pytest.raises(ValidationError, match="Payload must be a dictionary"):
            block.update_payload("not a dict")

        assert block.payload == {"text": "old"}

    def test_update_payload_accepts_empty_dict(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "old"},
        )

        block.update_payload({})

        assert block.payload == {}


class TestContentBlockReorder:
    def test_reorder_updates_order(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "x"},
        )

        block.reorder(5)

        assert block.order == 5

    def test_reorder_accepts_zero(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=10,
            payload={"text": "x"},
        )

        block.reorder(0)

        assert block.order == 0

    def test_reorder_raises_on_negative(self):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            order=0,
            payload={"text": "x"},
        )

        with pytest.raises(ValidationError, match="Order cannot be negative"):
            block.reorder(-1)

        assert block.order == 0
