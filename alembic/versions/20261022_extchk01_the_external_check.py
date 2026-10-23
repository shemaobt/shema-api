"""the Checagem externa: one record per approved version, opened by the team

One row per release, created by the team's first open with the version's parts and frases
copied from the stored packet, and never closed (ADR 0082). A new table, so nothing to backfill.

Revision ID: 20261022_extchk01
Revises: 20261021_opfor01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261022_extchk01"
down_revision = "20261021_opfor01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ir_external_checks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("release_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("device_id", sa.String(length=64), nullable=True),
        sa.Column("takes", sa.JSON(), nullable=False),
        sa.Column("frases", sa.JSON(), nullable=False),
        sa.Column("archive_id", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("release_id", name="uq_ir_external_checks_release"),
    )
    op.create_index("ix_ir_external_checks_session_id", "ir_external_checks", ["session_id"])


def downgrade() -> None:
    op.drop_table("ir_external_checks")
