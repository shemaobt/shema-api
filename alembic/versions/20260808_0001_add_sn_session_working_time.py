"""add sn_session_ticks and sn_sessions.net_working_seconds

The net working time the SPA has computed since the pilot, moved off ``localStorage``.
There it dies with the browser profile — a cleared storage, another machine or a second
seat all lose it — and it is the one number a facilitator's record is expected to keep.

Two objects, because the total and the evidence for it are different things. The counter
on ``sn_sessions`` is what every read wants. The ticks are what make it re-derivable
rather than merely believed: a lone counter can only be trusted, a log of stamped beats
can be recomputed.

``net_working_seconds`` is a plain integer count of seconds and deliberately NOT an
INTERVAL. Tests run on SQLite and production on Postgres, and duration is the one type
guaranteed to behave differently in the two — SQLAlchemy emulates ``Interval`` on SQLite
and maps it natively here, so a suite that agreed on durations would still disagree in
production. A count of seconds means the same thing everywhere. It is NOT NULL with a
server default of 0 because every existing session has to answer this question, and
"nobody has ticked yet" is zero, not unknown.

``sn_session_ticks`` carries a session, a client-minted idempotency key and a
server-stamped instant, and nothing else. That poverty is the point: §14 forbids
telemetry on listener behaviour, so this records that the session was open, never what
was done in it. A column with room for the latter is where that line gets crossed.

``occurred_at`` is stamped by the database's own clock, never by a client and never by
the application. A client clock is the one thing an accumulating counter must not trust —
skewed or edited, it becomes hours of working time nobody worked, on a laptop nobody
audits. The application's clock is barely better here: Cloud Run is multi-instance, so
two consecutive beats can be stamped by two containers that disagree. The database is the
only clock they all share.

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
    # The cursor the accumulation compare-and-swaps on, on the same row as the counter it
    # moves. Deriving the gap from a separate read of sn_session_ticks would derive it
    # under a snapshot the UPDATE does not share, and two heartbeats racing that read
    # charge the same stretch twice. Nullable, and null is meaningful: no stretch to
    # measure from. Completing a session sets it back to null, which is what stops a
    # closed session's pause from ever being charged.
    op.add_column(
        "sn_sessions",
        sa.Column("last_working_tick_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "sn_session_ticks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        # The client's own opaque string, unique within the session only. It is minted by
        # a client that has no idea what other sessions exist, so a global unique would
        # collide on values that never meant to be compared.
        sa.Column("client_tick_id", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        # CASCADE, not SET NULL: a tick is arithmetic about one session, not evidence
        # about a person, and outliving its session would leave rows that add up to
        # nothing.
        sa.ForeignKeyConstraint(["session_id"], ["sn_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # What makes a replayed beat a no-op instead of a second gap. The service reads
        # for the duplicate first and normally never reaches this, but the read and the
        # insert are two statements and a simultaneous duplicate passes both — so this is
        # the guard that actually holds, and because the charge is in the same
        # transaction it is rolled back with the rejected insert rather than left behind.
        #
        # Its index is also the only one this table gets. That lookup is the single query
        # that runs against it: the running total lives on sn_sessions, so nothing reads
        # these rows in time order on any hot path. A second index would be paid for on
        # every heartbeat insert, all session long, and read by nothing.
        sa.UniqueConstraint(
            "session_id", "client_tick_id", name="uq_sn_session_ticks_session_client"
        ),
    )


def downgrade() -> None:
    op.drop_table("sn_session_ticks")
    op.drop_column("sn_sessions", "last_working_tick_at")
    op.drop_column("sn_sessions", "net_working_seconds")
