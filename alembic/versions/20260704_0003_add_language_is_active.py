"""add is_active column to languages

Revision ID: 20260704_0003
Revises: 20260911_shema07
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260704_0003"
down_revision: str | None = "20260911_shema07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "languages",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("languages", "is_active")
