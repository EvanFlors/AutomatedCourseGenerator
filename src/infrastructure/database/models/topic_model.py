from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.content_block_model import ContentBlockModel
    from src.infrastructure.database.models.module_model import ModuleModel


class TopicModel(Base):
    __tablename__ = "topics"
    __table_args__ = (
        Index("ix_topics_module_id_order", "module_id", "order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    module_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    module: Mapped["ModuleModel"] = relationship(
        "ModuleModel",
        back_populates="topics",
    )
    blocks: Mapped[list["ContentBlockModel"]] = relationship(
        "ContentBlockModel",
        back_populates="topic",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ContentBlockModel.order",
    )
