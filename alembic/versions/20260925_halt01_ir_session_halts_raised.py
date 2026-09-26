"""how many halts a session has raised, so one halt can be told from the next

Revision ID: 20260925_halt01
Revises: 20260916_spine01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260925_halt01"
down_revision = "20260916_spine01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_sessions",
        sa.Column("halts_raised", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("ir_sessions", "halts_raised")
