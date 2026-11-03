"""ir_takes keeps the scene rehearsal a part was joined from: origin (ENG-1207)

Null on every existing row: no part was joined before this.

Revision ID: 20261019_join01
Revises: 20261019_retel01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261019_join01"
down_revision = "20261019_retel01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ir_takes") as batch:
        batch.add_column(sa.Column("origin", sa.String(length=36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ir_takes") as batch:
        batch.drop_column("origin")
