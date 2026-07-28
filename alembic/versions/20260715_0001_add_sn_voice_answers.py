"""add sn_voice_answers

One spoken Mapeamento answer per row, keyed by the question it answers. The bytes are a
WebM/Opus object in the private bucket; this row is the pointer the listing reads to
tell the screen which questions are answered.

Creates only the sn_* table. This database is shared with every other Tripod app, so
nothing here alters or drops anything it did not create.

Revision ID: 20260715_0001
Revises: 20260714_0003
Create Date: 2026-07-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260715_0001"
down_revision: str | None = "20260714_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sn_voice_answers",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("resource_path", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(["session_id"], ["sn_sessions.id"], ondelete="CASCADE"),
        # One answer per question (O5); re-recording replaces the row in place.
        sa.PrimaryKeyConstraint("session_id", "resource_path"),
    )


def downgrade() -> None:
    op.drop_table("sn_voice_answers")
