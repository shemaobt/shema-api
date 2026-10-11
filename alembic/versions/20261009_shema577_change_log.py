"""the change log: every PME write that kept no author now keeps one

Revision ID: 20261009_shema577
Revises: 20261008_shema578
Create Date: 2026-10-09

OBT-577 — Karina, via Daniel, 6/out/2026: *"toda alteração seja gravada, datada e com o nome de
quem alterou."* ``shema_change_log`` is one row per act on a subject that had no ledger of its
own (an intercessor, a member, a meeting log, a link, a pending project, an import). It holds
the keys an act touched and **no value**. Append-only by ``shema_reject_write()``, re-issued with
``CREATE OR REPLACE`` as ``20260927_shema543`` does; no foreign key on its account or project
columns, for the reason that revision gives.

The parent is `20261008_shema578`, read with ``alembic heads`` in this worktree on 9/out/2026.
Written by hand like every revision here, and plain PostgreSQL.
"""

import sqlalchemy as sa

from alembic import op

revision = "20261009_shema577"
down_revision = "20261008_shema578"
branch_labels = None
depends_on = None

APPEND_ONLY_FUNCTION = (
    "CREATE OR REPLACE FUNCTION shema_reject_write() RETURNS trigger AS $$ "
    "BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql"
)


def upgrade() -> None:
    op.create_table(
        "shema_change_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.String(120), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("project_id", sa.String(120), nullable=True),
        sa.Column("region_key", sa.String(40), nullable=True),
        sa.Column("field_keys", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_shema_change_log_occurred_at", "shema_change_log", ["occurred_at"])
    op.create_index("ix_shema_change_log_project", "shema_change_log", ["project_id", "occurred_at"])
    op.create_index("ix_shema_change_log_region", "shema_change_log", ["region_key", "occurred_at"])

    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER shema_change_log_append_only "
        "BEFORE UPDATE OR DELETE ON shema_change_log "
        "FOR EACH ROW EXECUTE FUNCTION shema_reject_write()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS shema_change_log_append_only ON shema_change_log")
    op.drop_index("ix_shema_change_log_region", table_name="shema_change_log")
    op.drop_index("ix_shema_change_log_project", table_name="shema_change_log")
    op.drop_index("ix_shema_change_log_occurred_at", table_name="shema_change_log")
    op.drop_table("shema_change_log")
