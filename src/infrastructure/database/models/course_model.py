from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infrastructure.database.models.module_model import ModuleModel


class CourseModel(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    modules: Mapped[list["ModuleModel"]] = relationship(
        "ModuleModel",
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ModuleModel.order",
    )
