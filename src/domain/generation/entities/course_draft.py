from uuid import uuid4

from src.domain.course.enums.block_type import BlockType
from src.domain.shared.exceptions.validation_error import ValidationError


class DraftBlock:
    """A single content block inside a draft topic."""

    def __init__(
        self,
        block_type: BlockType | str,
        content: str,
        *,
        order: int = 0,
    ):
        self.id = str(uuid4())
        self.block_type = (
            BlockType(block_type) if isinstance(block_type, str) else block_type
        )
        self.content = content.strip()
        self.order = order
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.block_type, BlockType):
            raise ValidationError(
                f"block_type must be a BlockType, got {type(self.block_type).__name__}."
            )
        if not self.content:
            raise ValidationError("DraftBlock content cannot be empty.")
        if self.order < 0:
            raise ValidationError("DraftBlock order cannot be negative.")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "block_type": self.block_type.value,
            "content": self.content,
            "order": self.order,
        }


class DraftTopic:
    """A topic inside a draft module."""

    def __init__(
        self,
        title: str,
        blocks: list[DraftBlock] | None = None,
        *,
        order: int = 0,
    ):
        self.id = str(uuid4())
        self.title = title.strip()
        self.blocks = list(blocks) if blocks else []
        self.order = order
        self._validate()

    def _validate(self) -> None:
        if not self.title:
            raise ValidationError("DraftTopic title cannot be empty.")
        if self.order < 0:
            raise ValidationError("DraftTopic order cannot be negative.")

    def add_block(self, block: DraftBlock) -> None:
        self.blocks.append(block)

    def remove_block(self, block_id: str) -> None:
        self.blocks = [b for b in self.blocks if b.id != block_id]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "order": self.order,
            "blocks": [b.to_dict() for b in self.blocks],
        }


class DraftModule:
    """A module inside a draft course."""

    def __init__(
        self,
        title: str,
        topics: list[DraftTopic] | None = None,
        *,
        order: int = 0,
    ):
        self.id = str(uuid4())
        self.title = title.strip()
        self.topics = list(topics) if topics else []
        self.order = order
        self._validate()

    def _validate(self) -> None:
        if not self.title:
            raise ValidationError("DraftModule title cannot be empty.")
        if self.order < 0:
            raise ValidationError("DraftModule order cannot be negative.")

    def add_topic(self, topic: DraftTopic) -> None:
        self.topics.append(topic)

    def remove_topic(self, topic_id: str) -> None:
        self.topics = [t for t in self.topics if t.id != topic_id]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "order": self.order,
            "topics": [t.to_dict() for t in self.topics],
        }


class CourseDraft:
    """The LLM-generated course structure, built iteratively.

    This is a pure data structure — not a domain aggregate — so the
    generator and evaluator agents can mutate it freely without
    triggering entity validation on every change. It is converted
    to domain entities only when the evaluator approves.
    """

    def __init__(
        self,
        title: str,
        level: str,
        description: str | None = None,
        modules: list[DraftModule] | None = None,
        target_audience: str | None = None,
        learning_objectives: list[str] | None = None,
    ):
        self.title = title.strip()
        self.level = level
        self.description = description.strip() if description else None
        self.modules = list(modules) if modules else []
        self.target_audience = (
            target_audience.strip() if target_audience else None
        )
        self.learning_objectives = list(learning_objectives) if learning_objectives else []

    def add_module(self, module: DraftModule) -> None:
        self.modules.append(module)

    def remove_module(self, module_id: str) -> None:
        self.modules = [m for m in self.modules if m.id != module_id]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "level": self.level,
            "description": self.description,
            "target_audience": self.target_audience,
            "learning_objectives": self.learning_objectives,
            "modules": [m.to_dict() for m in self.modules],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CourseDraft":
        modules = [
            DraftModule(
                title=m["title"],
                order=m.get("order", i),
                topics=[
                    DraftTopic(
                        title=t["title"],
                        order=t.get("order", j),
                        blocks=[
                            DraftBlock(
                                block_type=b["block_type"],
                                content=b["content"],
                                order=b.get("order", k),
                            )
                            for k, b in enumerate(t.get("blocks", []))
                        ],
                    )
                    for j, t in enumerate(m.get("topics", []))
                ],
            )
            for i, m in enumerate(data.get("modules", []))
        ]
        return cls(
            title=data.get("title", ""),
            level=data.get("level", ""),
            description=data.get("description"),
            target_audience=data.get("target_audience"),
            learning_objectives=data.get("learning_objectives", []),
            modules=modules,
        )
