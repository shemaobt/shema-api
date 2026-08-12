"""add ir_sessions and ir_prompts

The internalization room's own tables. Until now the room's pedagogy lived inside the
Flutter app — the facilitator lines, the Meaning Map and the coverage rule were compiled
into the binary, so changing a single spoken line meant a new store submission and the
map existed in two copies. These two tables move that ownership to the server.

`ir_sessions` mirrors `ph_interviews`: the conversation and the coverage tracker ride as
JSON rather than as child tables, because neither is queried across sessions — they are
read and rewritten whole, once per turn.

`ir_prompts` holds one row per voiced or internal role. The bodies are seeded from the
markdown files next to the service, so git keeps the history and the database keeps the
editable copy; a row absent here simply falls back to the file.

Creates only ir_* tables. This database is shared with every other Tripod app, so
nothing here alters or drops anything it did not create.

Revision ID: 20260807_0001
Revises: 20260731_0001
Create Date: 2026-08-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260807_0001"
down_revision: str | None = "20260731_0001"
branch_labels: str | None = None
depends_on: str | None = None


_PROMPT_KEY_ENUM = sa.Enum(
    "guide",
    "validator",
    "coverage_classifier",
    "book_panorama",
    "draft_self_check",
    "bt_analyst",
    "bt_verdict_speaker",
    name="ir_prompt_key_enum",
)

_SESSION_STATUS_ENUM = sa.Enum(
    "in_progress",
    "done",
    "needs_person",
    name="ir_session_status_enum",
)


def upgrade() -> None:
    op.create_table(
        "ir_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("pericope", sa.String(length=120), nullable=False),
        sa.Column("status", _SESSION_STATUS_ENUM, nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("coverage_state", sa.JSON(), nullable=False),
        sa.Column("kept_takes", sa.JSON(), nullable=False),
        sa.Column("back_translation", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ir_sessions_status_created", "ir_sessions", ["status", "created_at"])

    op.create_table(
        "ir_prompts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("key", _PROMPT_KEY_ENUM, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ir_prompts_key", "ir_prompts", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ir_prompts_key", table_name="ir_prompts")
    op.drop_table("ir_prompts")
    op.drop_index("ix_ir_sessions_status_created", table_name="ir_sessions")
    op.drop_table("ir_sessions")
    bind = op.get_bind()
    _PROMPT_KEY_ENUM.drop(bind, checkfirst=True)
    _SESSION_STATUS_ENUM.drop(bind, checkfirst=True)
