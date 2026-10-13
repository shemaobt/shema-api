"""ir_sessions.kept_takes defaults to {}: the code stops writing it before it is dropped

Only session creation wrote it, always {}, and nothing read it. The code that no longer maps
it inserts sessions without it, while the revision still serving during the deploy reads it,
so the column stays until that revision is gone and a later migration drops it.

Revision ID: 20261013_scene02
Revises: 20261013_scene01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261013_scene02"
down_revision = "20261013_scene01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ir_sessions") as batch:
        batch.alter_column("kept_takes", existing_type=sa.JSON(), server_default="{}")


def downgrade() -> None:
    with op.batch_alter_table("ir_sessions") as batch:
        batch.alter_column("kept_takes", existing_type=sa.JSON(), server_default=None)
