"""ir_sessions keeps the retelling verdict of each turn: retellings (ENG-1378)

Null on every existing row: no verdict was kept before this.

Revision ID: 20261019_retel01
Revises: 20261016_demo01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261019_retel01"
down_revision = "20261016_demo01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ir_sessions") as batch:
        batch.add_column(sa.Column("retellings", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ir_sessions") as batch:
        batch.drop_column("retellings")
