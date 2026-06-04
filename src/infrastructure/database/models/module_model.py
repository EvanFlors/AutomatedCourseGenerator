from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.course_model import CourseModel
    from src.infrastructure.database.models.topic_model import TopicModel


class ModuleModel(Base):
    __tablename__ = "modules"
    __table_args__ = (
        Index("ix_modules_course_id_order", "course_id", "order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped["CourseModel"] = relationship(
        "CourseModel",
        back_populates="modules",
    )
    topics: Mapped[list["TopicModel"]] = relationship(
        "TopicModel",
        back_populates="module",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TopicModel.order",
    )
