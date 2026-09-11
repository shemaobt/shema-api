"""the record's lifecycle: a version to save against, a saver to name, and the edit trail

Revision ID: 20260911_shema02
Revises: 20260911_shema01
Create Date: 2026-09-11

The parent is `20260911_shema01`, read with `uv run alembic heads` in this worktree
immediately before this file was written. It is BE-02's revision and it is the head of this
branch's own base (BE-05's branch), not of `origin/dev` — three issues in wave 7 branch from
here and author migrations against *this* head, so whoever the user merges second re-points.
The pull request body says so; `docs/resource_requests.md` §8.3 is why that sentence is worth
writing down rather than remembering.

Written by hand, like the other 98 revisions here: `alembic/env.py` imports only
`app.core.database`, so its metadata is empty and `--autogenerate` would emit a migration
dropping every existing table (`docs/resource_requests.md` §8.1).

**Three columns and one table, and the three columns are the half that needs saying.**
`version` is `NOT NULL` with a server default of `1`, so the 127 records a seed will write —
and any row already in a deployed database — start at a version a client can save against
rather than at NULL, which no `If-Match` could match. `updated_by` and `updated_by_name` are
the saver, and both are honestly empty for a record nobody in this product has saved yet:
`SET NULL` on the account rather than `RESTRICT`, because unlike the trail's `changed_by`
this one is the *current* pointer and a deleted account must not make a record unreadable —
the accountability copy is the name beside it and the rows in `shema_record_edits`, which do
restrict.

**Nothing backfills.** `updated_by_name` gets `''` and not a stand-in author: a record whose
saver is unknown says so, and the alternative is a migration asserting that somebody saved
something.

The append-only trigger reuses `shema_reject_write()`, created by `20260911_shema01` with
`CREATE OR REPLACE`. It is re-issued here rather than assumed, because a downgrade of that
revision drops the function while this one's trigger would still name it — and a `CREATE OR
REPLACE` of an identical body costs nothing. The downgrade drops only this revision's
trigger and leaves the function standing, since `shema_progress_history` and
`shema_role_changes` still use it.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260911_shema02"
down_revision = "20260911_shema01"
branch_labels = None
depends_on = None

APPEND_ONLY_FUNCTION = (
    "CREATE OR REPLACE FUNCTION shema_reject_write() RETURNS trigger AS $$ "
    "BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql"
)


def upgrade() -> None:
    op.add_column(
        "shema_projects",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "shema_projects",
        sa.Column(
            "updated_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "shema_projects",
        sa.Column("updated_by_name", sa.String(200), nullable=False, server_default=""),
    )

    op.create_table(
        "shema_record_edits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("field_key", sa.String(80), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column(
            "changed_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("changed_by_name", sa.String(200), nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_shema_record_edits_project_version", "shema_record_edits", ["project_id", "version"]
    )
    op.create_index("ix_shema_record_edits_changed_at", "shema_record_edits", ["changed_at"])

    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER shema_record_edits_append_only "
        "BEFORE UPDATE OR DELETE ON shema_record_edits "
        "FOR EACH ROW EXECUTE FUNCTION shema_reject_write()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS shema_record_edits_append_only ON shema_record_edits")
    op.drop_index("ix_shema_record_edits_changed_at", table_name="shema_record_edits")
    op.drop_index("ix_shema_record_edits_project_version", table_name="shema_record_edits")
    op.drop_table("shema_record_edits")

    op.drop_column("shema_projects", "updated_by_name")
    op.drop_column("shema_projects", "updated_by")
    op.drop_column("shema_projects", "version")
