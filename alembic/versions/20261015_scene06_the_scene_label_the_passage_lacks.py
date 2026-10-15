"""ir_scene_rehearsals remembers the scene label the passage lacks: scene_foreign

No backfill: a label the passage lacked was kept as no label until now, so there is nothing
to recover and a null says what those rows held.

Revision ID: 20261015_scene06
Revises: 20261014_ocsrc01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261015_scene06"
down_revision = "20261014_ocsrc01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ir_scene_rehearsals") as batch:
        batch.add_column(sa.Column("scene_foreign", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ir_scene_rehearsals") as batch:
        batch.drop_column("scene_foreign")
