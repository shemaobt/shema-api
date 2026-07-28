"""add oc_acousteme_artifacts table

Revision ID: 20260709_0001
Revises: 20260609_0001
Create Date: 2026-07-09 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260709_0001"
down_revision: str | None = "20260609_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oc_acousteme_artifacts",
        sa.Column("audio_id", sa.String(length=64), nullable=False),
        sa.Column("codebook_version", sa.String(length=64), nullable=False),
        sa.Column("collection", sa.String(length=64), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("gcs_bucket", sa.String(length=255), nullable=False),
        sa.Column("gcs_object", sa.Text(), nullable=False),
        sa.Column("content_encoding", sa.String(length=20), nullable=False),
        sa.Column("audio_bucket", sa.String(length=255), nullable=True),
        sa.Column("audio_object", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("num_frames", sa.Integer(), nullable=True),
        sa.Column("hop_sec", sa.Float(), nullable=True),
        sa.Column("num_segments", sa.Integer(), nullable=True),
        sa.Column("num_units", sa.Integer(), nullable=True),
        sa.Column("distinct_units", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("audio_id", "codebook_version"),
    )
    op.create_index(
        op.f("ix_oc_acousteme_artifacts_collection"),
        "oc_acousteme_artifacts",
        ["collection"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oc_acousteme_artifacts_status"),
        "oc_acousteme_artifacts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_oc_acousteme_artifacts_status"),
        table_name="oc_acousteme_artifacts",
    )
    op.drop_index(
        op.f("ix_oc_acousteme_artifacts_collection"),
        table_name="oc_acousteme_artifacts",
    )
    op.drop_table("oc_acousteme_artifacts")
