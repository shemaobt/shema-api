"""the turn claim says whether it was taken for the session's opening

No backfill: a claim stored before reads as a team turn's, which is what an older instance's
opening claim reads as while the deploy runs (ADR 0079).

Revision ID: 20261021_opfor01
Revises: 20261021_forced01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_opfor01"
down_revision = "20261021_forced01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions",
        sa.Column(
            "claimed_for_the_opening",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("ir_sessions", "claimed_for_the_opening")
