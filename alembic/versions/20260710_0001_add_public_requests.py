"""add public_requests table

Revision ID: 20260710_0001
Revises: 20260609_0001
Create Date: 2026-07-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0001"
down_revision: str | None = "20260609_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("requester_name", sa.String(length=200), nullable=False),
        sa.Column("requester_email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=3), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language_id", sa.String(length=36), nullable=True),
        sa.Column("new_language_name", sa.String(length=200), nullable=True),
        sa.Column("new_language_code", sa.String(length=3), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_entity_id", sa.String(length=36), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_public_requests_kind", "public_requests", ["kind"])
    op.create_index("ix_public_requests_status", "public_requests", ["status"])
    op.create_index("ix_public_requests_requester_email", "public_requests", ["requester_email"])
    op.create_index("ix_public_requests_code", "public_requests", ["code"])


def downgrade() -> None:
    op.drop_index("ix_public_requests_code", table_name="public_requests")
    op.drop_index("ix_public_requests_requester_email", table_name="public_requests")
    op.drop_index("ix_public_requests_status", table_name="public_requests")
    op.drop_index("ix_public_requests_kind", table_name="public_requests")
    op.drop_table("public_requests")
