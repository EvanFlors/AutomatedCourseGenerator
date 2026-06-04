from uuid import uuid4

from src.domain.course.entities.content_block import ContentBlock
from src.domain.shared.exceptions.validation_error import ValidationError


class Topic:

    def __init__(
        self,
        title: str,
        order: int,
        blocks: list[ContentBlock] | None = None,
        id: str | None = None,
    ):

        self.id = id or str(uuid4())

        self.title = title.strip()

        self.order = order

        self.blocks = blocks or []

        self._validate()

    def _validate(self):

        if not self.title:
            raise ValidationError("Topic title cannot be empty.")

        if self.order < 0:
            raise ValidationError("Topic order cannot be negative.")

    def add_block(self, block: ContentBlock):

        self.blocks.append(block)

        self._sort_blocks()

    def remove_block(self, block_id: str):

        self.blocks = [
            block for block in self.blocks
            if block.id != block_id
        ]

    def get_block(self, block_id: str):

        return next(
            (
                block
                for block in self.blocks
                if block.id == block_id
            ),
            None
        )

    def _sort_blocks(self):

        self.blocks.sort(key=lambda block: block.order)