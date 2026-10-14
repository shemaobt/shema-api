"""ir_sessions.kept_takes is dropped: no revision still serving names it

The downgrade restores the column as '{}' on every row, which is what every row held.

Revision ID: 20261014_scene05
Revises: 20261013_scene04
"""

import sqlalchemy as sa

from alembic import op

revision = "20261014_scene05"
down_revision = "20261013_scene04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ir_sessions") as batch:
        batch.drop_column("kept_takes")


def downgrade() -> None:
    with op.batch_alter_table("ir_sessions") as batch:
        batch.add_column(sa.Column("kept_takes", sa.JSON(), nullable=False, server_default="{}"))
