"""add course_generation_jobs table

Revision ID: 8c2a4f9b1d3e
Revises: d3819966c2dc
Create Date: 2026-06-03 12:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "8c2a4f9b1d3e"
down_revision: Union[str, None] = "d3819966c2dc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_generation_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("concepts_extracted", sa.Integer(), nullable=False),
        sa.Column("relations_extracted", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_course_generation_jobs_course_id"),
        "course_generation_jobs",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_course_generation_jobs_status"),
        "course_generation_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_course_generation_jobs_course_created",
        "course_generation_jobs",
        ["course_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_course_generation_jobs_course_created",
        table_name="course_generation_jobs",
    )
    op.drop_index(
        op.f("ix_course_generation_jobs_status"),
        table_name="course_generation_jobs",
    )
    op.drop_index(
        op.f("ix_course_generation_jobs_course_id"),
        table_name="course_generation_jobs",
    )
    op.drop_table("course_generation_jobs")
