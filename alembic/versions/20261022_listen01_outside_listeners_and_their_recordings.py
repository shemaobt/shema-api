"""the outside listeners of a Checagem externa, their recordings and their marks

Each listener is the next number of the check's version under a unique index, each recording
is attached only once its bytes are in the bucket, and each mark is one «está boa» on one frase
(ADR 0083). Three new tables, so nothing to backfill.

Revision ID: 20261022_listen01
Revises: 20261022_extchk01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261022_listen01"
down_revision = "20261022_extchk01"
branch_labels = None
depends_on = None


def _now(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "ir_external_listeners",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("check_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        _now("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archive_id", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("check_id", "number", name="uq_ir_external_listeners_check_number"),
    )
    op.create_table(
        "ir_external_recordings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("listener_id", sa.String(length=36), nullable=False),
        sa.Column("check_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("crc32c", sa.String(length=16), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        _now("stored_at"),
        sa.Column("archive_id", sa.String(length=36), nullable=True),
        sa.UniqueConstraint(
            "listener_id", "sha256", name="uq_ir_external_recordings_listener_sha256"
        ),
    )
    op.create_table(
        "ir_external_marks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("listener_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=False),
        _now("marked_at"),
        sa.Column("archive_id", sa.String(length=36), nullable=True),
        sa.UniqueConstraint(
            "listener_id", "segment_id", name="uq_ir_external_marks_listener_segment"
        ),
    )
    for table, column in (
        ("ir_external_listeners", "check_id"),
        ("ir_external_listeners", "session_id"),
        ("ir_external_recordings", "listener_id"),
        ("ir_external_recordings", "session_id"),
        ("ir_external_marks", "listener_id"),
        ("ir_external_marks", "session_id"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("ir_external_marks")
    op.drop_table("ir_external_recordings")
    op.drop_table("ir_external_listeners")
