"""the earlier passages a session was opened with, as her runner sends them

Revision ID: 20261002_earl01
Revises: 20261002_open01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261002_earl01"
down_revision = "20261002_open01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ir_sessions", sa.Column("earlier_passages", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ir_sessions", "earlier_passages")
