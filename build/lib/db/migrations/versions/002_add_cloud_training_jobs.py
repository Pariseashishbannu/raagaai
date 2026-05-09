"""Add cloud_training_jobs table for cloud model training.

Revision ID: 002
Revises: 001
Create Date: 2026-03-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create cloud_training_jobs table."""
    op.create_table(
        "cloud_training_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),  # aws|gcp|azure
        sa.Column("cloud_job_id", sa.String(500), nullable=True, index=True),
        sa.Column("platform_logs_url", sa.String(500), nullable=True),
        sa.Column("platform_model_uri", sa.String(500), nullable=True),
        sa.Column("job_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), server_default="submitted", index=True),
        sa.Column("progress", sa.Float(), server_default="0.0"),
        sa.Column("current_stage", sa.String(100), nullable=True),
        sa.Column("config_json", postgresql.JSONB(), server_default="{}"),
        sa.Column("model_download_url", sa.String(500), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("use_custom_credentials", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add index for user_id and status lookups
    op.create_index(
        "ix_cloud_training_jobs_user_status",
        "cloud_training_jobs",
        ["user_id", "status"],
    )


def downgrade() -> None:
    """Drop cloud_training_jobs table."""
    op.drop_index("ix_cloud_training_jobs_user_status")
    op.drop_table("cloud_training_jobs")
