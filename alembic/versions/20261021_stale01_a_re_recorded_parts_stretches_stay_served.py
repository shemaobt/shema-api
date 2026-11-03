"""ir_segments marks the stretches retired because their part was recorded again (ENG-1739)

Every row stored until now keeps `stale` false: the rows retired before this revision were
never told apart from the ones a replacement or a telling-back started over retired, so none
of them is served as a stretch waiting to be told again.

Revision ID: 20261021_stale01
Revises: 20261019_takerec01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_stale01"
down_revision = "20261019_takerec01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ir_segments") as batch:
        batch.add_column(
            sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("ir_segments") as batch:
        batch.drop_column("stale")
