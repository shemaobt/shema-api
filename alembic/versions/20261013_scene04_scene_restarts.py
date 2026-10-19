"""A scene rehearsal's restarts, the attempt each frase names, and the restart that set it aside

Revision ID: 20261013_scene04
Revises: 20261013_scene03
"""

import sqlalchemy as sa

from alembic import op

revision = "20261013_scene04"
down_revision = "20261013_scene03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_scene_restarts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("rehearsal_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column(
            "restarted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("archive_id", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("rehearsal_id", "n", name="uq_ir_scene_restarts_rehearsal_n"),
    )
    op.create_index("ix_ir_scene_restarts_rehearsal_id", "ir_scene_restarts", ["rehearsal_id"])
    op.create_index("ix_ir_scene_restarts_session_id", "ir_scene_restarts", ["session_id"])
    op.add_column("ir_scene_frases", sa.Column("attempt", sa.String(length=36), nullable=True))
    op.add_column("ir_scene_frases", sa.Column("restart_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("ir_scene_frases", "restart_id")
    op.drop_column("ir_scene_frases", "attempt")
    op.drop_table("ir_scene_restarts")
