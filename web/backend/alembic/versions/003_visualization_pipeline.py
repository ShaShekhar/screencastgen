"""Add visualization pipeline type.

Revision ID: 003
Revises: 002
Create Date: 2026-05-12
"""
from typing import Sequence, Union

from alembic import op


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE pipeline_type ADD VALUE IF NOT EXISTS 'visualization'")
    op.alter_column("jobs", "uploaded_file_id", nullable=True)


def downgrade() -> None:
    op.alter_column("jobs", "uploaded_file_id", nullable=False)
    # PostgreSQL enum values cannot be removed without recreating the type.
