"""A scene rehearsal's frases, each with its place in the scene recording

Revision ID: 20261013_scene03
Revises: 20261013_scene02
"""

import sqlalchemy as sa

from alembic import op

revision = "20261013_scene03"
down_revision = "20261013_scene02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_scene_frases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("rehearsal_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("starts_ms", sa.Integer(), nullable=False),
        sa.Column("ends_ms", sa.Integer(), nullable=False),
        sa.Column("replaces_id", sa.String(length=36), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("crc32c", sa.String(length=16), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("archive_id", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("rehearsal_id", "sha256", name="uq_ir_scene_frases_rehearsal_sha256"),
    )
    op.create_index("ix_ir_scene_frases_rehearsal_id", "ir_scene_frases", ["rehearsal_id"])
    op.create_index("ix_ir_scene_frases_session_id", "ir_scene_frases", ["session_id"])


def downgrade() -> None:
    op.drop_table("ir_scene_frases")
