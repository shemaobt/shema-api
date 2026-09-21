"""add new-language fields to change_requests

Revision ID: 20260714_0102
Revises: 20260714_0101
Create Date: 2026-07-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0102"
down_revision: str | None = "20260714_0101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("change_requests", sa.Column("new_language_name", sa.String(200), nullable=True))
    op.add_column("change_requests", sa.Column("new_language_code", sa.String(3), nullable=True))


def downgrade() -> None:
    op.drop_column("change_requests", "new_language_code")
    op.drop_column("change_requests", "new_language_name")
