"""add change_requests table and language created_by

Revision ID: 20260714_0101
Revises: 20260911_shema07
Create Date: 2026-07-14

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0101"
down_revision: str | None = "20260911_shema07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False, index=True),
        sa.Column(
            "requester_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("code", sa.String(3), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "language_id",
            sa.String(36),
            sa.ForeignKey("languages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "grant_manager_access",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "reviewed_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text, nullable=True),
        sa.Column("created_entity_id", sa.String(36), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column("languages", sa.Column("created_by", sa.String(36), nullable=True))
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
    op.drop_table("change_requests")
