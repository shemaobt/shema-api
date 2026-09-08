"""the moment somebody arrived at a halted room

A halted room shows something to press when a person walks in, and the press reached nothing:
the server did not know somebody was standing there, so neither did the Desk, and two
facilitators could walk to the same room while a third waited.

On the session and not on the device because it is the session's halt being answered. A tablet
with no session has no session to stamp, and its device halt is already the signal — which is
why ENG-792's device columns are the revision before this one rather than beside it.

Nullable and not backfilled: a room nobody walked into must not read as one somebody did.

Revision ID: 20260908_arr02
Revises: 20260908_arr01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260908_arr02"
down_revision = "20260908_arr01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions", sa.Column("person_arrived_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ir_sessions", "person_arrived_at")
