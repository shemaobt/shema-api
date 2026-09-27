"""shema eten: the reports the server answered, and who set a manual credit

Revision ID: 20260927_shema_eten01
Revises: 20260917_0001
Create Date: 2026-09-27

The parent is `20260917_0001`, read with `uv run alembic heads` in this worktree on 27/sep/2026
immediately before this file was written — the measurement `docs/shema.md` §7.1 asks for. Five
sibling issues of the same batch author migrations against `dev` too, and this one is declared
to merge last, so whoever merges it re-points `down_revision` at the head standing then; the pull
request body says so. The id is `shema_eten01` rather than the next `shemaNN` on purpose: two
branches coining the same number is how `shema02` had to become `shema07`.

Why BE-11 needs a migration at all, when `completed_date` and `shema_eten_credits` already
exist: the issue's DoD asks that reports **snapshot the data they were computed from** — *a
report run in March and re-run in June will differ… only if it is recorded which data produced
which figure* — and there was nowhere to record a report. `shema_eten_reports` is that place,
append-only by the trigger `shema_progress_history` already uses (the function exists since
`20260911_shema01`). And a manual credit overrides a funder-facing number, so the ledger now
names who set it: `recorded_by` (`SET NULL`, the row is mutable) and the name as it was then.

Written by hand like every revision in this directory: `alembic/env.py` imports only
`app.core.database`, so `--autogenerate` sees no metadata (`docs/resource_requests.md` §8.1).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260927_shema_eten01"
down_revision = "20260917_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shema_eten_credits",
        sa.Column(
            "recorded_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "shema_eten_credits",
        sa.Column("recorded_by_name", sa.String(200), nullable=False, server_default=""),
    )

    op.create_table(
        "shema_eten_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("scope_key", sa.String(200), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column(
            "computed_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("computed_by_name", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_shema_eten_reports_year_scope_created",
        "shema_eten_reports",
        ["year", "scope_key", "created_at"],
    )
    op.execute(
        "CREATE TRIGGER shema_eten_reports_append_only BEFORE UPDATE OR DELETE "
        "ON shema_eten_reports FOR EACH ROW EXECUTE FUNCTION shema_reject_write()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS shema_eten_reports_append_only ON shema_eten_reports")
    op.drop_index("ix_shema_eten_reports_year_scope_created", table_name="shema_eten_reports")
    op.drop_table("shema_eten_reports")
    op.drop_column("shema_eten_credits", "recorded_by_name")
    op.drop_column("shema_eten_credits", "recorded_by")
