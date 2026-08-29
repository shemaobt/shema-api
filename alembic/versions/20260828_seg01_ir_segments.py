"""add ir_segments: a told-back stretch as a thing with its own address

A stretch used to be a line in the JSON list on ``ir_sessions.back_translation``, so the only
way to name one in the world was its position in that list. Correcting a single stretch — which
recording explains it, which slice of that recording, which version counts, what it was divided
out of — had nowhere to live.

**This redefines rather than migrates.** There is no production data on this path (owner
decision, 27/08/2026), so nothing carries the old ``chunks`` array into the new table: a session
that already held stretches simply has none here, which is the same state as a session that
never told anything back.

Creates only ``ir_segments``. This database is shared with every other Tripod app, so nothing
here alters or drops anything it did not create — the JSON column the stretches used to live in
is left exactly where it is.

The two indexes worth reading twice are partial: a position belongs to one **current** stretch,
so a replaced one and its replacement may share a position while only the replacement counts.
Written for PostgreSQL and for the SQLite the test suite builds, because both support it and a
constraint that exists on only one of them is a rule nobody can rely on.

There are two because a unique index treats NULLs as distinct, so the one over
``(session_id, parent_id, ordinal)`` enforces nothing for a stretch nobody divided — which is
most of them. The second one covers exactly those. Measured against this migration's own
database rather than assumed.

Revision ID: 20260828_seg01
Revises: 20260823_join4
Create Date: 2026-08-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260828_seg01"
down_revision: str | None = "20260823_join4"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ir_segments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("take_id", sa.String(length=36), nullable=False),
        sa.Column("starts_ms", sa.Integer(), nullable=False),
        sa.Column("ends_ms", sa.Integer(), nullable=False),
        sa.Column("pass_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bridge_take_id", sa.String(length=36), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ir_segments_session_id", "ir_segments", ["session_id"])
    op.create_index("ix_ir_segments_project_id", "ir_segments", ["project_id"])
    op.create_index("ix_ir_segments_parent_id", "ir_segments", ["parent_id"])
    op.create_index("ix_ir_segments_take_id", "ir_segments", ["take_id"])
    op.create_index(
        "ix_ir_segments_session_current", "ir_segments", ["session_id", "superseded_at"]
    )
    op.create_index(
        "uq_ir_segments_position",
        "ir_segments",
        ["session_id", "parent_id", "ordinal"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL"),
        sqlite_where=sa.text("superseded_at IS NULL"),
    )
    op.create_index(
        "uq_ir_segments_root_position",
        "ir_segments",
        ["session_id", "ordinal"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL AND parent_id IS NULL"),
        sqlite_where=sa.text("superseded_at IS NULL AND parent_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ir_segments_root_position", table_name="ir_segments")
    op.drop_index("uq_ir_segments_position", table_name="ir_segments")
    op.drop_index("ix_ir_segments_session_current", table_name="ir_segments")
    op.drop_index("ix_ir_segments_take_id", table_name="ir_segments")
    op.drop_index("ix_ir_segments_parent_id", table_name="ir_segments")
    op.drop_index("ix_ir_segments_project_id", table_name="ir_segments")
    op.drop_index("ix_ir_segments_session_id", table_name="ir_segments")
    op.drop_table("ir_segments")
