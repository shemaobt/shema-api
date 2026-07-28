"""add sound-necklace session tables

Creates only the sn_* tables and their enum types. This database is shared with
every other Tripod app, so nothing here alters or drops anything it did not create.

Revision ID: 20260714_0001
Revises: 20260713_0001
Create Date: 2026-07-14 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0001"
down_revision: str | None = "20260713_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sn_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("audio_ref", sa.String(length=255), nullable=False),
        sa.Column("story_name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("manifest_id", sa.String(length=64), nullable=False),
        sa.Column(
            "granularity_level",
            sa.Enum("small", "medium", "large", name="sn_granularity_level_enum"),
            nullable=False,
        ),
        sa.Column("bead_sec", sa.Float(), nullable=False),
        sa.Column("pipeline_consent", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("in_progress", "completed", name="sn_session_status_enum"),
            nullable=False,
        ),
        sa.Column(
            "current_step",
            sa.Enum(
                "listen",
                "cut",
                "triage",
                "phrases",
                "conversation",
                "save",
                name="sn_session_step_enum",
            ),
            nullable=False,
        ),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sn_sessions_project_id"), "sn_sessions", ["project_id"], unique=False)
    op.create_index(op.f("ix_sn_sessions_created_by"), "sn_sessions", ["created_by"], unique=False)

    # The state document is the SPA's, stored as the exact bytes it sent: TEXT, never
    # jsonb — jsonb discards key order and whitespace, and the client re-validates the
    # document under a strict schema. `version` backs the autosave compare-and-swap.
    op.create_table(
        "sn_session_state",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sn_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )


def downgrade() -> None:
    op.drop_table("sn_session_state")
    op.drop_index(op.f("ix_sn_sessions_created_by"), table_name="sn_sessions")
    op.drop_index(op.f("ix_sn_sessions_project_id"), table_name="sn_sessions")
    op.drop_table("sn_sessions")

    bind = op.get_bind()
    bind.execute(sa.text("DROP TYPE IF EXISTS sn_session_step_enum"))
    bind.execute(sa.text("DROP TYPE IF EXISTS sn_session_status_enum"))
    bind.execute(sa.text("DROP TYPE IF EXISTS sn_granularity_level_enum"))
