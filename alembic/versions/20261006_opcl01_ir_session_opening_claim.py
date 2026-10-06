"""the claim on a session's opening: whose turn id drafts it, and since when

No backfill: a session stored before has no claim standing, which is what two nulls say
(ADR 0053).

Revision ID: 20261006_opcl01
Revises: 20261006_zera01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261006_opcl01"
down_revision = "20261006_zera01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions", sa.Column("opening_claim_turn_id", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "ir_sessions", sa.Column("opening_claimed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ir_sessions", "opening_claimed_at")
    op.drop_column("ir_sessions", "opening_claim_turn_id")
