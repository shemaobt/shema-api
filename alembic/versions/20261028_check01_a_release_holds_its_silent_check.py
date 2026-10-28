"""a release holds the verdict of its silent check (ENG-1799)

Nullable, and left null on every row stored until now: a release approved before this revision
was never checked, and writing a verdict for it would invent the record this column keeps.

Revision ID: 20261028_check01
Revises: 20261022_swap01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261028_check01"
down_revision = "20261022_swap01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ir_releases", sa.Column("release_check", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ir_releases") as batch:
        batch.drop_column("release_check")
