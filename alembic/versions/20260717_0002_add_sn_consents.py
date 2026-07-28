"""add sn_consents

Consent as queryable evidence of a lawful basis (§12 / O6), rather than a boolean on the
session. The row is the authority; sn_sessions.pipeline_consent stays, write-only — the SPA
sends it on create and reads its own copy out of the state document, and no response has
ever carried it. record_consent keeps the two from contradicting each other.

Both enum values ship in this first migration on purpose. The Colar records two speakers
— the story and the listener whose voice answers 21+ questions — and adding the second
value later would mean an ALTER TYPE on the database six production apps share, to say
something already known today. The oral consent audio §12 admits does NOT ship here: it is
a nullable column on our own table, the cheap ALTER-later case, and it comes with the
upload route that fills it rather than sitting empty as a shape to migrate around.

Creates only the sn_* table and its enum type. This database is shared with every other
Tripod app, so nothing here alters or drops anything it did not create.

Revision ID: 20260717_0002
Revises: 20260717_0001
Create Date: 2026-07-17 02:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_0002"
down_revision: str | None = "20260717_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sn_consents",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column(
            "type",
            sa.Enum("pipeline_use", "voice_answers", name="sn_consent_type_enum"),
            nullable=False,
        ),
        # Nullable, and SET NULL below: the evidence outlives the account that typed it.
        sa.Column("confirmed_by", sa.String(length=36), nullable=True),
        # No server_default: the value is assigned in Python. A re-confirmation changes no
        # other column, and the ORM emits no UPDATE at all when nothing is dirty — an
        # onupdate here would leave the record misdating itself.
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sn_sessions.id"], ondelete="CASCADE"),
        # SET NULL, never CASCADE: a second facilitator can re-confirm a consent on
        # somebody else's session, and under CASCADE deleting that account would erase the
        # evidence while the session still stands. RESTRICT is not the answer either —
        # `users` is shared with every other Tripod app, and a consent row here must not be
        # what makes deleting a user fail over there.
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        # One record per consent: re-confirming updates it rather than stacking a second.
        sa.PrimaryKeyConstraint("session_id", "type"),
    )


def downgrade() -> None:
    op.drop_table("sn_consents")

    # drop_table does not drop the TYPE create_table implicitly created, and leaving it
    # behind makes the next upgrade fail on a type that already exists.
    bind = op.get_bind()
    bind.execute(sa.text("DROP TYPE IF EXISTS sn_consent_type_enum"))
