"""add created_by column to languages

Revision ID: 20260704_0004
Revises: 20260704_0003
Create Date: 2026-07-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260704_0004"
down_revision: str | None = "20260704_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "languages",
        sa.Column("created_by", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_languages_created_by_users",
        "languages",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_languages_created_by_users", "languages", type_="foreignkey")
    op.drop_column("languages", "created_by")
