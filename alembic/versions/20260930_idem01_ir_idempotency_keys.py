"""the answer a chunk or a correction settled, kept under the tablet's Idempotency-Key

Revision ID: 20260930_idem01
Revises: 20260929_warn01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260930_idem01"
down_revision = "20260929_warn01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_idempotency_keys",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("route", sa.String(length=255), primary_key=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("claim", sa.String(length=36), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("body", sa.LargeBinary(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ir_idempotency_keys")
