"""add updated_at column to languages

Revision ID: 20260704_0002
Revises: 20260609_0001
Create Date: 2026-07-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260704_0002"
down_revision: str | None = "20260609_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "languages",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    op.execute("UPDATE languages SET updated_at = created_at")
    op.alter_column("languages", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("languages", "updated_at")
