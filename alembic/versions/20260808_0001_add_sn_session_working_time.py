"""add sn_session_ticks and sn_sessions.net_working_seconds

Adds the two columns a session's net working time accumulates on and the log of
heartbeats it is derived from. What the shapes mean and why they were chosen is
documented with the code that uses them, in
``app/services/sound_necklace/working_time.py`` and ``app/db/models/sound_necklace.py``.

``net_working_seconds`` is NOT NULL with a server default of 0, because every session
that already exists has to answer this question and "nobody has ticked yet" is zero, not
unknown. ``last_working_tick_at`` is nullable, and null is the value a session starts and
restarts at.

CASCADE on the session, unlike the audit events next door: these rows are not evidence
about a person, they are the arithmetic behind one session's number. Once the session is
gone there is nothing left for them to add up to.

Creates only sn_* objects. This database is shared with every other Tripod app, so
nothing here alters or drops anything it did not create.

Revision ID: 20260808_0001
Revises: 20260731_0001
Create Date: 2026-08-08 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0001"
down_revision: str | None = "20260731_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sn_sessions",
        sa.Column("net_working_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "sn_sessions",
        sa.Column("last_working_tick_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "sn_session_ticks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("client_tick_id", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sn_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "client_tick_id", name="uq_sn_session_ticks_session_client"
        ),
    )


def downgrade() -> None:
    op.drop_table("sn_session_ticks")
    op.drop_column("sn_sessions", "last_working_tick_at")
    op.drop_column("sn_sessions", "net_working_seconds")
