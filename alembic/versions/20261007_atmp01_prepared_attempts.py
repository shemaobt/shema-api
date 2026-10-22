"""the attempts a prepared opening was drafted in, kept beside the line until it is taken

No backfill: a line prepared before has no attempts to keep, which is what a null says
(ADR 0054).

Revision ID: 20261007_atmp01
Revises: 20261007_keep01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261007_atmp01"
down_revision = "20261007_keep01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ir_sessions", sa.Column("prepared_attempts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ir_sessions", "prepared_attempts")
