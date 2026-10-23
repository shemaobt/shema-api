"""a grain switch sets the earlier grain's takes aside (ENG-1765)

The session keeps the grain the team chose and when the switch reached the server, and a take
the time a switch set it aside. Every stored row reads null, which is a session never switched,
so nothing is backfilled.

A take a switch set aside leaves the take's two unique indexes, so the same bytes kept again at
the grain in force are a new row sharing the stored object. The downgrade restores the old
constraint and index, and fails loudly, deleting nothing, once a session holds such a pair.

Revision ID: 20261022_grain01
Revises: 20261022_listen01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261022_grain01"
down_revision = "20261022_listen01"
branch_labels = None
depends_on = None

BY_BYTES = "uq_ir_takes_session_kind_sha256"
BY_KEY = "uq_ir_takes_session_storage_key"
DECLARED_PARTS_SKIPPED = "sha256 <> ''"
SET_ASIDE_SKIPPED = "set_aside_at IS NULL"


def _unique(name: str, columns: list[str], where: str) -> None:
    op.create_index(
        name,
        "ir_takes",
        columns,
        unique=True,
        postgresql_where=sa.text(where),
        sqlite_where=sa.text(where),
    )


def upgrade() -> None:
    with op.batch_alter_table("ir_sessions") as batch:
        batch.add_column(sa.Column("grain", sa.String(8), nullable=True))
        batch.add_column(sa.Column("grain_switched_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("ir_takes") as batch:
        batch.add_column(sa.Column("set_aside_at", sa.DateTime(timezone=True), nullable=True))
        batch.drop_constraint(BY_KEY, type_="unique")
    op.drop_index(BY_BYTES, table_name="ir_takes")
    _unique(BY_KEY, ["session_id", "storage_key"], SET_ASIDE_SKIPPED)
    _unique(
        BY_BYTES,
        ["session_id", "kind", "sha256"],
        f"{DECLARED_PARTS_SKIPPED} AND {SET_ASIDE_SKIPPED}",
    )


def downgrade() -> None:
    op.drop_index(BY_BYTES, table_name="ir_takes")
    op.drop_index(BY_KEY, table_name="ir_takes")
    _unique(BY_BYTES, ["session_id", "kind", "sha256"], DECLARED_PARTS_SKIPPED)
    with op.batch_alter_table("ir_takes") as batch:
        batch.create_unique_constraint(BY_KEY, ["session_id", "storage_key"])
        batch.drop_column("set_aside_at")
    with op.batch_alter_table("ir_sessions") as batch:
        batch.drop_column("grain_switched_at")
        batch.drop_column("grain")
