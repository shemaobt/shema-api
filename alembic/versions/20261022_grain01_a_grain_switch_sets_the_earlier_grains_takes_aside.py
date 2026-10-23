"""a grain switch sets the earlier grain's takes aside (ENG-1765)

The session keeps the grain the team chose and when the switch reached the server, and a take
the time a switch set it aside. Every stored row reads null, which is a session never switched,
so nothing is backfilled.

Revision ID: 20261022_grain01
Revises: 20261022_listen01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261022_grain01"
down_revision = "20261022_listen01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ir_sessions") as batch:
        batch.add_column(sa.Column("grain", sa.String(8), nullable=True))
        batch.add_column(sa.Column("grain_switched_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("ir_takes") as batch:
        batch.add_column(sa.Column("set_aside_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ir_takes") as batch:
        batch.drop_column("set_aside_at")
    with op.batch_alter_table("ir_sessions") as batch:
        batch.drop_column("grain_switched_at")
        batch.drop_column("grain")
