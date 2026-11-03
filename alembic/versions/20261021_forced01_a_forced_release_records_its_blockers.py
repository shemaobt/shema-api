"""a forced release records the blockers it passed (ENG-1305, ADR 0075)

Nullable, and left null on every row stored until now: a release forced before this revision
passed the two blockers the narrower force waived, but which of them stood is not on the row,
and writing a guess would invent the record this column exists to keep.

Revision ID: 20261021_forced01
Revises: 20261021_stale01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_forced01"
down_revision = "20261021_stale01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ir_releases", sa.Column("forced_blockers", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ir_releases") as batch:
        batch.drop_column("forced_blockers")
