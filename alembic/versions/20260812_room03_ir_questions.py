"""the hand's questions, addressed to a person and outliving the session

Revision ID: 20260812_room03
Revises: 20260812_room02
"""

import sqlalchemy as sa
from alembic import op

revision = "20260812_room03"
down_revision = "20260812_room02"
branch_labels = None
depends_on = None

STATUS = sa.Enum("open", "answered", "resolved", name="ir_question_status_enum")


def upgrade() -> None:
    # `create_table` mints the enum type itself; creating it here too fails the second run.
    op.create_table(
        "ir_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(64), nullable=False, index=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("pericope", sa.String(120), nullable=False),
        sa.Column("audio_key", sa.String(512), nullable=False),
        sa.Column("status", STATUS, nullable=False, server_default="open"),
        sa.Column("reply_audio_key", sa.String(512), nullable=True),
        sa.Column("answered_by", sa.String(36), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heard_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ir_questions_status_created", "ir_questions", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ir_questions_status_created", table_name="ir_questions")
    op.drop_table("ir_questions")
    STATUS.drop(op.get_bind(), checkfirst=True)
