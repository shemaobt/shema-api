"""a scene rehearsal laid in again at a new pass is a new take, sharing its bytes (ENG-1407)

A joined take is the same take only under the same bytes, number and pass, so joined rows may
share a stored object; a take recorded as itself still holds its bytes and its key once per
session. Takes a grain switch set aside stay outside every index (ADR 0096). Reversible until a
session holds two takes of the same bytes: the old index then fails loudly on the way down, and
no take is deleted.

Revision ID: 20261022_swap01
Revises: 20261022_grain01
"""

import sqlalchemy as sa

from alembic import op

revision = "20261022_swap01"
down_revision = "20261022_grain01"
branch_labels = None
depends_on = None

TABLE = "ir_takes"
KEY = "uq_ir_takes_session_storage_key"
BYTES = "uq_ir_takes_session_kind_sha256"
JOINED = "uq_ir_takes_session_joined_pass"
STANDING = "set_aside_at IS NULL"
WITH_BYTES = f"sha256 <> '' AND {STANDING}"
ORDINAL_OR_NONE = sa.text("coalesce(ordinal, -1)")
PASS_OR_NONE = sa.text("coalesce(pass_number, -1)")


def _unique(name: str, columns: list[str | sa.TextClause], where: str) -> None:
    op.create_index(
        name,
        TABLE,
        columns,
        unique=True,
        postgresql_where=sa.text(where),
        sqlite_where=sa.text(where),
    )


def upgrade() -> None:
    op.drop_index(BYTES, table_name=TABLE)
    op.drop_index(KEY, table_name=TABLE)
    _unique(KEY, ["session_id", "storage_key"], f"origin IS NULL AND {STANDING}")
    _unique(BYTES, ["session_id", "kind", "sha256"], f"origin IS NULL AND {WITH_BYTES}")
    _unique(
        JOINED,
        ["session_id", "kind", "sha256", ORDINAL_OR_NONE, PASS_OR_NONE],
        f"origin IS NOT NULL AND {WITH_BYTES}",
    )


def downgrade() -> None:
    op.drop_index(JOINED, table_name=TABLE)
    op.drop_index(BYTES, table_name=TABLE)
    op.drop_index(KEY, table_name=TABLE)
    _unique(KEY, ["session_id", "storage_key"], STANDING)
    _unique(BYTES, ["session_id", "kind", "sha256"], WITH_BYTES)
