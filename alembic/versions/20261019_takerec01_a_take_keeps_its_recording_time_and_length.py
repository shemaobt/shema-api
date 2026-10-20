"""ir_takes keeps its recording time, length and clock offset, and its bytes once (ENG-1273)

Every stored take and scene rehearsal is given its upload time as its recording time, which is
what was served as one until now; no length and no offset. The unique index over a session's
kind and hash skips the declared parts, whose hash is empty.

Revision ID: 20261019_takerec01
Revises: 20261019_join01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261019_takerec01"
down_revision = "20261019_join01"
branch_labels = None
depends_on = None

INDEX = "uq_ir_takes_session_kind_sha256"
DECLARED_PARTS_SKIPPED = sa.text("sha256 <> ''")


def _recorded_at_from_created_at(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(f"UPDATE {table} SET recorded_at = created_at")
    with op.batch_alter_table(table) as batch:
        batch.alter_column(
            "recorded_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )


def upgrade() -> None:
    _recorded_at_from_created_at("ir_takes")
    with op.batch_alter_table("ir_takes") as batch:
        batch.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("device_clock_offset_ms", sa.BigInteger(), nullable=True))
    op.create_index(
        INDEX,
        "ir_takes",
        ["session_id", "kind", "sha256"],
        unique=True,
        postgresql_where=DECLARED_PARTS_SKIPPED,
        sqlite_where=DECLARED_PARTS_SKIPPED,
    )
    _recorded_at_from_created_at("ir_scene_rehearsals")


def downgrade() -> None:
    with op.batch_alter_table("ir_scene_rehearsals") as batch:
        batch.drop_column("recorded_at")
    op.drop_index(INDEX, table_name="ir_takes")
    with op.batch_alter_table("ir_takes") as batch:
        batch.drop_column("device_clock_offset_ms")
        batch.drop_column("duration_ms")
        batch.drop_column("recorded_at")
