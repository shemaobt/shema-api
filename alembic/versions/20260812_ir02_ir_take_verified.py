"""record that a stored take was read back from the bucket and matched

Revision ID: 20260812_ir02
Revises: 20260812_ir01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260812_ir02"
down_revision = "20260812_ir01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ir_takes", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("ir_takes", "verified_at")
