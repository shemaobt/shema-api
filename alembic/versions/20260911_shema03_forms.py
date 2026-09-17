"""form definitions, and the two columns that make a submission readable a year from now

Revision ID: 20260911_shema03
Revises: 20260911_shema02
Create Date: 2026-09-11

The parent is `20260911_shema02`, read with `uv run alembic heads` in this worktree
immediately before this file was written. It is BE-06's revision and it is the head of this
branch's own base, not of `origin/dev`: BE-07, BE-08 and BE-12 branch from it in one wave and
each may author a revision against this same head, so **whoever the user merges second
re-points**. The declared merge order is 07, 08, 12 and this one is third; the pull request
body says so, which is where `docs/resource_requests.md` §8.3 asks for it — that document
records a parent that moved four times while a stack sat in review, and the failure is
invisible where it is written, because a stacked PR's CI runs against its own base.

Written by hand, like the other 99 revisions here: `alembic/env.py` imports only
`app.core.database`, so its metadata is empty and `--autogenerate` would emit a migration
dropping every existing table (`docs/resource_requests.md` §8.1).

**One table and six columns, and the table is the one that needs the argument.** A form
definition edited in place rewrites the meaning of every answer already given to it — the
words are gone and the answers now read against words nobody answered. So the spec is
published as a version, by content, and never edited; `shema_submissions.definition_id` and
`shema_intake_links.definition_id` are what make *which version* a fact of the row rather than
a guess from a timestamp.

**The five added columns are `NOT NULL` with no backfill, and that is safe for a stated
reason rather than by luck.** `shema_submissions` and `shema_intake_links` were created two
revisions ago by `20260911_shema01`, nothing has written to either — the module had no
endpoint that could — and this revision is in the same stack, ahead of any deploy of it. A
backfill here would have to invent a definition version for a submission that answered one,
which is precisely the fiction the table exists to prevent.

`downgrade()` is not decorative: `migrations.yml` walks the newest revision down and back up
on a real PostgreSQL, and it drops the columns before the table they point at, because the
foreign keys are the reason the order matters.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260911_shema03"
down_revision = "20260911_shema02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shema_form_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_shema_form_definitions_kind_version",
        "shema_form_definitions",
        ["kind", "version"],
        unique=True,
    )
    op.create_index(
        "uq_shema_form_definitions_kind_content",
        "shema_form_definitions",
        ["kind", "content_hash"],
        unique=True,
    )

    op.add_column(
        "shema_submissions",
        sa.Column(
            "definition_id",
            sa.String(36),
            sa.ForeignKey("shema_form_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.add_column(
        "shema_submissions",
        sa.Column(
            "intake_link_id",
            sa.String(36),
            sa.ForeignKey("shema_intake_links.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("shema_submissions", sa.Column("archived_payload", sa.Text(), nullable=False))
    op.add_column(
        "shema_submissions", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.add_column(
        "shema_intake_links",
        sa.Column(
            "definition_id",
            sa.String(36),
            sa.ForeignKey("shema_form_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("shema_intake_links", "definition_id")

    op.drop_column("shema_submissions", "applied_at")
    op.drop_column("shema_submissions", "archived_payload")
    op.drop_column("shema_submissions", "intake_link_id")
    op.drop_column("shema_submissions", "definition_id")

    op.drop_index("uq_shema_form_definitions_kind_content", table_name="shema_form_definitions")
    op.drop_index("uq_shema_form_definitions_kind_version", table_name="shema_form_definitions")
    op.drop_table("shema_form_definitions")
