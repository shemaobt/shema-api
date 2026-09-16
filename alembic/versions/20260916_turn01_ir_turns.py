"""the table that lets a resent turn find its own answer instead of repeating it

Revision ID: 20260916_turn01
Revises: 20260911_rel02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260916_turn01"
down_revision = "20260911_rel02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_turns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False, index=True),
        sa.Column("turn_id", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("session_id", "turn_id", name="uq_ir_turns_session_turn"),
    )


def downgrade() -> None:
    op.drop_table("ir_turns")
