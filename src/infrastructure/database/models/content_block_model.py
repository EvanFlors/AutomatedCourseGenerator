from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.topic_model import TopicModel


class ContentBlockModel(Base):
    __tablename__ = "content_blocks"
    __table_args__ = (
        Index("ix_content_blocks_topic_id_order", "topic_id", "order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    topic: Mapped["TopicModel"] = relationship(
        "TopicModel",
        back_populates="blocks",
    )
