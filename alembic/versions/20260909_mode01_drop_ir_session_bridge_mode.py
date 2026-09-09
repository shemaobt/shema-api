"""drop the column that stored the conversation's mode

The tablet named a working method on `createSession`, the room wrote it here, and every
turn afterwards was shaped by it. Marcia's doctrine lists app-owned modes of the
conversation among the things that fail the build: the Guide decides how to work with a
team from what the team just said, and a column deciding it in advance is the opposite of
that. Nothing reads or writes this any more, and a column with a `server_default` goes on
stamping a mode onto every session opened while it exists.

The downgrade re-adds it exactly as `20260819_room08` did, with the same
`calibration_pending` server default. It cannot restore what the rows were carrying —
that goes with the column — and it does not pretend to: every row comes back holding the
pending value each of them was born with.

Revision ID: 20260909_mode01
Revises: 20260908_arr02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260909_mode01"
down_revision = "20260908_arr02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("ir_sessions", "bridge_mode")


def downgrade() -> None:
    op.add_column(
        "ir_sessions",
        sa.Column(
            "bridge_mode",
            sa.String(length=24),
            nullable=False,
            server_default="calibration_pending",
        ),
    )
