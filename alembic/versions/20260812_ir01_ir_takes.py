"""the audio the team must not lose: ensaio takes and back-translation chunks

Revision ID: 20260812_ir01
Revises: 20260811_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "20260812_ir01"
down_revision = "20260811_0004"
branch_labels = None
depends_on = None

KIND = sa.Enum("ensaio", "retro", name="ir_take_kind_enum")


def upgrade() -> None:
    op.create_table(
        "ir_takes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False, index=True),
        sa.Column("device_id", sa.String(64), nullable=False, index=True),
        sa.Column("team_id", sa.String(36), nullable=True, index=True),
        sa.Column("pericope", sa.String(120), nullable=False),
        sa.Column("kind", KIND, nullable=False),
        sa.Column("scope", sa.String(120), nullable=False),
        sa.Column("pass_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("crc32c", sa.String(16), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_unique_constraint(
        "uq_ir_takes_session_storage_key", "ir_takes", ["session_id", "storage_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_ir_takes_session_storage_key", "ir_takes", type_="unique")
    op.drop_table("ir_takes")
    KIND.drop(op.get_bind(), checkfirst=True)
