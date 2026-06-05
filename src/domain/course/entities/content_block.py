from uuid import uuid4

from src.domain.course.enums.block_type import BlockType
from src.domain.shared.exceptions.validation_error import ValidationError


class ContentBlock:

    def __init__(
        self,
        block_type: BlockType,
        order: int,
        payload: dict,
        id: str | None = None,
    ):
        self.id = id or str(uuid4())
        self.type = block_type
        self.order = order
        self.payload = payload
        self._validate()

    def _validate(self):

        if self.order < 0:
            raise ValidationError("Block order cannot be negative.")

        if not isinstance(self.payload, dict):
            raise ValidationError("Payload must be a dictionary.")

    def update_payload(self, payload: dict):

        if not isinstance(payload, dict):
            raise ValidationError("Payload must be a dictionary.")

        self.payload = payload

    def reorder(self, new_order: int):

        if new_order < 0:
            raise ValidationError("Order cannot be negative.")

        self.order = new_order