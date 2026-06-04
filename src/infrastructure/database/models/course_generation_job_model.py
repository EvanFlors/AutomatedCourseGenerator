from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base

if TYPE_CHECKING:
    pass


class CourseGenerationJobModel(Base):
    __tablename__ = "course_generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )

    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    concepts_extracted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    relations_extracted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    __table_args__ = (
        Index(
            "ix_course_generation_jobs_course_created",
            "course_id",
            "created_at",
        ),
    )
