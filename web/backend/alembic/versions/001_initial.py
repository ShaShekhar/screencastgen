"""Initial migration - create uploaded_files and jobs tables.

Revision ID: 001
Revises: None
Create Date: 2026-04-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uploaded_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("original_name", sa.String(512), nullable=False),
        sa.Column("stored_path", sa.String(1024), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    pipeline_type = sa.Enum("audio", "highlight", "lipsync", name="pipeline_type")
    job_status = sa.Enum("pending", "running", "completed", "failed", name="job_status")

    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_type", pipeline_type, nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="pending"),
        sa.Column("progress_current", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_phase", sa.String(64), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("config_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("uploaded_file_id", UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id"), nullable=False),
        sa.Column("ref_audio_file_id", UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id"), nullable=True),
        sa.Column("ref_video_file_id", UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id"), nullable=True),
        sa.Column("output_path", sa.String(1024), nullable=True),
        sa.Column("celery_task_id", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("uploaded_files")
    sa.Enum(name="pipeline_type").drop(op.get_bind())
    sa.Enum(name="job_status").drop(op.get_bind())
