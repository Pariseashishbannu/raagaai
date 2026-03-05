"""Initial schema — users, ragas, talas, generation_jobs, compositions.

Revision ID: 001
Revises: None
Create Date: 2026-02-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(20), server_default="free"),
        sa.Column("monthly_generations_used", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ragas",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name_english", sa.String(200), nullable=False),
        sa.Column("name_telugu", sa.String(200), nullable=True),
        sa.Column("melakarta_number", sa.Integer(), nullable=True),
        sa.Column("arohanam", postgresql.JSONB(), nullable=False),
        sa.Column("avarohanam", postgresql.JSONB(), nullable=False),
        sa.Column("varja_svaras", postgresql.JSONB(), server_default="[]"),
        sa.Column("characteristic_phrases", postgresql.JSONB(), server_default="[]"),
        sa.Column("gamaka_rules", postgresql.JSONB(), server_default="{}"),
        sa.Column("janya_of", sa.String(100), sa.ForeignKey("ragas.id"), nullable=True),
        sa.Column("rasa_tags", postgresql.JSONB(), server_default="[]"),
    )

    op.create_table(
        "talas",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("beats", sa.Integer(), nullable=False),
        sa.Column("jathi", sa.String(20), nullable=False),
        sa.Column("structure", postgresql.JSONB(), nullable=False),
    )

    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("raga_id", sa.String(100), sa.ForeignKey("ragas.id"), nullable=False),
        sa.Column("tala_id", sa.String(50), sa.ForeignKey("talas.id"), nullable=False),
        sa.Column("kala", sa.String(20), server_default="madhyama"),
        sa.Column("language", sa.String(20), server_default="telugu"),
        sa.Column("theme", sa.String(100), nullable=True),
        sa.Column("sections", sa.Integer(), server_default="3"),
        sa.Column("include_chittaswaram", sa.String(5), server_default="false"),
        sa.Column("status", sa.String(20), server_default="queued", index=True),
        sa.Column("current_stage", sa.String(50), nullable=True),
        sa.Column("progress", sa.Float(), server_default="0.0"),
        sa.Column("checkpoints", postgresql.JSONB(), server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "compositions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_jobs.id"), unique=True),
        sa.Column("raga_id", sa.String(100), sa.ForeignKey("ragas.id")),
        sa.Column("tala_id", sa.String(50), sa.ForeignKey("talas.id")),
        sa.Column("audio_key", sa.String(500)),
        sa.Column("notation_key", sa.String(500), nullable=True),
        sa.Column("sahityam", sa.Text(), nullable=True),
        sa.Column("svara_sequence", postgresql.JSONB()),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("is_public", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Indexes for hot queries
    op.create_index("idx_jobs_user_status", "generation_jobs", ["user_id", "status"])
    op.create_index("idx_jobs_status_created", "generation_jobs", ["status", "created_at"])
    op.create_index("idx_compositions_user", "compositions", ["user_id", "created_at"])
    op.create_index("idx_ragas_melakarta", "ragas", ["melakarta_number"])


def downgrade() -> None:
    op.drop_table("compositions")
    op.drop_table("generation_jobs")
    op.drop_table("talas")
    op.drop_table("ragas")
    op.drop_table("users")
