"""Zerar's archive: one row per Zerar, and a nullable stamp on the five tables of the work

No backfill: every row already stored is live, which is what a null stamp says (ADR 0047).

Revision ID: 20261006_zera01
Revises: 20261002_earl01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261006_zera01"
down_revision = "20261002_earl01"
branch_labels = None
depends_on = None

STAMPED = ("ir_sessions", "ir_takes", "ir_segments", "ir_coverage_events", "ir_releases")


def upgrade() -> None:
    op.create_table(
        "ir_archives",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("pericope", sa.String(length=120), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_by", sa.String(length=36), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
    )
    for table in STAMPED:
        op.add_column(table, sa.Column("archive_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    for table in STAMPED:
        op.drop_column(table, "archive_id")
    op.drop_table("ir_archives")
