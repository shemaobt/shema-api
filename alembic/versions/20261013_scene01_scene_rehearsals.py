"""The scene rehearsal's record: the scene recording as sent

A table of its own, stamped by a Zerar like the rest of a session's work (ADR 0059).

Revision ID: 20261013_scene01
Revises: 20261012_spine02
"""

import sqlalchemy as sa

from alembic import op

revision = "20261013_scene01"
down_revision = "20261012_spine02"
branch_labels = None
depends_on = None


def _recording() -> list[sa.Column]:
    return [
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("crc32c", sa.String(length=16), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "ir_scene_rehearsals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("pericope", sa.String(length=120), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        *_recording(),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("scene", sa.String(length=16), nullable=True),
        sa.Column("scene_said", sa.String(length=16), nullable=True),
        sa.Column("scene_guess", sa.String(length=16), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_turn_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("archive_id", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("session_id", "sha256", name="uq_ir_scene_rehearsals_session_sha256"),
        sa.UniqueConstraint("session_id", "n", name="uq_ir_scene_rehearsals_session_n"),
    )
    op.create_index("ix_ir_scene_rehearsals_session_id", "ir_scene_rehearsals", ["session_id"])
    op.create_index("ix_ir_scene_rehearsals_project_id", "ir_scene_rehearsals", ["project_id"])


def downgrade() -> None:
    op.drop_table("ir_scene_rehearsals")
