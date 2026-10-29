"""a replaced take keeps the server's time it stopped being live (ENG-1256)

Nullable, and left null on every take stored until now: the moment a take stopped being live was
never kept, and writing one for it would invent the record this column holds.

Revision ID: 20261029_stamp01
Revises: 20261028_check01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261029_stamp01"
down_revision = "20261028_check01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ir_takes", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("ir_takes", "superseded_at")
