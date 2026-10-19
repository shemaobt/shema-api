"""projects remembers which team is the demo team: is_demo_team (ADR 0064)

False on every existing row: no team was the demo team before this.

Revision ID: 20261016_demo01
Revises: 20261015_scene06
"""

import sqlalchemy as sa

from alembic import op

revision = "20261016_demo01"
down_revision = "20261015_scene06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column("is_demo_team", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("is_demo_team")
