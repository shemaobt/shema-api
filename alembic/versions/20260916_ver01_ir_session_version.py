"""the optimistic check that stops one turn's evidence erasing another's

A turn commits `messages` and `comprehension` as whole-value JSON, each computed from
whatever the writer had read. Two turns landing together for one session raced the same
row with no way to tell the later commit that an earlier one had already moved it, so the
later write stood and the earlier turn's evidence was gone with nobody told (ENG-643).

`server_default` so a row written by a caller that does not name the column still gets one
instead of a NOT NULL failure or a silent null already lost the fight, the way `comprehension`
itself had to be fixed for the same reason.

Revision ID: 20260916_ver01
Revises: 20260916_turn01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260916_ver01"
down_revision = "20260916_turn01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("ir_sessions", "version")
