"""shema_exports: who exported which projects, when, over which scope

Revision ID: 20260930_shema403
Revises: 20260930_shema547
Create Date: 2026-09-30

OBT-403 (BE-14). The parent was `20260929_shema541` when this file was written (30/sep/2026);
OBT-547 authored `20260930_shema547` on the same parent in the same batch and merged into `dev`
first, and this file was re-pointed to it — the head `alembic heads` read after merging, a
measurement rather than a value to remember (`docs/shema.md` §7.1). The id carries the issue
number, as `shema524`, `shema531`, `shema541` and `shema543` do, so two siblings cannot mint the
same `shemaNN`.

The issue asks that exports be logged — *who exported what, when* — because once the file has
left, the trail is the only thing that can answer an after-the-fact question. One row per file,
append-only by the trigger function `shema_reject_write()` that `20260911_shema01` created and
`shema_eten_reports` already uses. The row keeps ids and counts and never text: a withdrawn
prayer request must not outlive its withdrawal in a table nobody can edit.

Written by hand and importing nothing from `app.`, like the other revisions: `alembic/env.py`
has empty metadata, and importing a model module builds an engine at import time.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260930_shema403"
down_revision: str | None = "20260930_shema547"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shema_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "exported_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("exported_by_name", sa.String(200), nullable=False),
        sa.Column("scope_key", sa.String(200), nullable=False),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("project_count", sa.Integer(), nullable=False),
        sa.Column("withheld_count", sa.Integer(), nullable=False),
        sa.Column("project_ids", sa.JSON(), nullable=False),
        sa.Column("request_ids", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_shema_exports_created_at", "shema_exports", ["created_at"])
    op.execute(
        "CREATE TRIGGER shema_exports_append_only BEFORE UPDATE OR DELETE "
        "ON shema_exports FOR EACH ROW EXECUTE FUNCTION shema_reject_write()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS shema_exports_append_only ON shema_exports")
    op.drop_index("ix_shema_exports_created_at", table_name="shema_exports")
    op.drop_table("shema_exports")
