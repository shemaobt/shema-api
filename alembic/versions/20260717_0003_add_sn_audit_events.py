"""add sn_audit_events

Who reached whose voice, and when (§12) — until now this existed only as structlog lines
that nothing could query. The events are written by the services that do the reaching, in
the same transaction, so there is never a signed URL issued without a row to say so.

Append-only by nature: nothing updates a row here, because an event is a thing that
happened. Both foreign keys to identity are SET NULL rather than CASCADE — deleting a user
must not erase the record of what that account reached, which is the one question this
table exists to answer and is asked most exactly when the account is gone.

Creates only the sn_* table and its enum type. This database is shared with every other
Tripod app, so nothing here alters or drops anything it did not create.

Revision ID: 20260717_0003
Revises: 20260717_0002
Create Date: 2026-07-17 03:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_0003"
down_revision: str | None = "20260717_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sn_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "event",
            sa.Enum(
                "audio_url_issued",
                "artifact_uploaded",
                "artifact_url_issued",
                "voice_url_issued",
                "session_completed",
                "session_reopened",
                "consent_recorded",
                name="sn_audit_event_enum",
            ),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        # The longest ref is an audio_id at 128 — NOT the voice path, which its allowlist
        # bounds at 93. 128 is a real number, not headroom: 20260713_0001 widened that
        # column from 64 because a Terena pilot slug hit 83, and ingestion caps ids at 128.
        # Do not tighten this below 128 on the strength of the voice path; a long-slug
        # audio would fail URL issuance on Postgres while SQLite stayed green.
        # The storage keys are NOT stored here — an artifact's is content-addressed and
        # moves under a re-upload, and the audio's object name is an unbounded Text column
        # upstream.
        sa.Column("resource_ref", sa.String(length=255), nullable=False),
        # 45 = the longest IPv6 form. Nothing writes it: behind Cloud Run's proxy there is
        # no address this API can honestly attribute to the caller. The column ships now
        # because adding it later is a migration on a shared production database.
        sa.Column("ip", sa.String(length=45), nullable=True),
        # SET NULL on both: an audit row must outlive the account it names and the session
        # it happened in. Under CASCADE, deleting the user would erase the evidence of what
        # they reached — the exact records an investigation wants.
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sn_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # One index, for the one query there is: a project's trail, newest first. It serves
    # the scope, the ORDER BY and the LIMIT together, so nothing sorts a table that only
    # ever grows — Postgres reads it backwards for DESC.
    #
    # `id` is in it for the tiebreak, and the listing orders DESC on both to match: a
    # mixed order (occurred_at DESC, id ASC) cannot be read off this index, and Postgres
    # would sort every one of a project's events before the LIMIT took a hundred. Verified
    # on a throwaway Postgres, not assumed.
    #
    # Deliberately NOT one index per column. Every INSERT here rides the hot path — a row
    # per URL issued — and pays for each index. `event` has seven values and narrows an
    # already-scoped query; `user_id` is filtered by nothing at all. Add them when a query
    # wants them.
    op.create_index(
        "ix_sn_audit_events_project_occurred",
        "sn_audit_events",
        ["project_id", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sn_audit_events_project_occurred", table_name="sn_audit_events")
    op.drop_table("sn_audit_events")

    # drop_table does not drop the TYPE create_table implicitly created, and leaving it
    # behind makes the next upgrade fail on a type that already exists.
    bind = op.get_bind()
    bind.execute(sa.text("DROP TYPE IF EXISTS sn_audit_event_enum"))
