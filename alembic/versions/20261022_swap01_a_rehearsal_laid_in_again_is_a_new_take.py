"""a scene rehearsal laid in again at a new pass is a new take, sharing its bytes (ENG-1407)

A joined take is the same take only under the same bytes, number and pass, so joined rows may
share a stored object; a take recorded as itself still holds its bytes and its key once per
session. Reversible until a session holds two takes of the same bytes: the old index then fails
loudly on the way down, and no take is deleted.

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
DECLARED_PARTS_SKIPPED = sa.text("sha256 <> ''")
RECORDED_AS_ITSELF = sa.text("origin IS NULL")
RECORDED_AS_ITSELF_WITH_BYTES = sa.text("sha256 <> '' AND origin IS NULL")
JOINED_WITH_BYTES = sa.text("origin IS NOT NULL AND sha256 <> ''")
ORDINAL_OR_NONE = sa.text("coalesce(ordinal, -1)")
PASS_OR_NONE = sa.text("coalesce(pass_number, -1)")


def _partial(name: str, columns: list[str | sa.TextClause], where: sa.TextClause) -> None:
    op.create_index(name, TABLE, columns, unique=True, postgresql_where=where, sqlite_where=where)


def upgrade() -> None:
    op.drop_index(BYTES, table_name=TABLE)
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(KEY, type_="unique")
    _partial(KEY, ["session_id", "storage_key"], RECORDED_AS_ITSELF)
    _partial(BYTES, ["session_id", "kind", "sha256"], RECORDED_AS_ITSELF_WITH_BYTES)
    _partial(
        JOINED,
        ["session_id", "kind", "sha256", ORDINAL_OR_NONE, PASS_OR_NONE],
        JOINED_WITH_BYTES,
    )


def downgrade() -> None:
    op.drop_index(JOINED, table_name=TABLE)
    op.drop_index(BYTES, table_name=TABLE)
    op.drop_index(KEY, table_name=TABLE)
    with op.batch_alter_table(TABLE) as batch:
        batch.create_unique_constraint(KEY, ["session_id", "storage_key"])
    _partial(BYTES, ["session_id", "kind", "sha256"], DECLARED_PARTS_SKIPPED)
