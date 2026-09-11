"""the health assessment says which questions it answered and who entered it

Revision ID: 20260911_shema04
Revises: 20260911_shema02
Create Date: 2026-09-11

The parent is `20260911_shema02`, read with `uv run alembic heads` in this worktree
immediately before this file was written. That is BE-06's revision and the head of this
branch's own base, not of `origin/dev`: BE-07, BE-08 and BE-12 all branch from it and author a
revision against the same head, so the graph forks the moment the second one reaches `dev` and
whoever the user merges second re-points their `down_revision` at the first. The declared merge
order is 07, 08, 12 — this is the first, so it re-parents nobody. The pull request body carries
the revision id so the other two can read it there rather than guess.

BE-15 renumbers this file's own revision id from `20260911_shema03` to `20260911_shema04`
before merging it beside BE-08's and BE-12's: all three were authored against the same
head and minted the identical literal id, which is not the ordinary multi-head fork this
docstring describes but a collision `alembic` cannot resolve with `merge heads` until the
ids differ. `down_revision` is untouched — it still names `20260911_shema02` — so the three
remain siblings and BE-15's own merge revision is what joins them, rather than a linear
re-pointing. The PR body carries the renumbering so whoever merges this branch's PR into
`dev` knows the id changed here.

Written by hand, like every other revision here: `alembic/env.py` imports only
`app.core.database`, so its metadata is empty and `--autogenerate` would emit a migration
dropping every existing table (`docs/resource_requests.md` §8.1).

**Three columns, and the nullability of each one is the decision.**

`question_set_version` is nullable **with no default**, and that is the same rule
`docs/shema.md` §7.4 protects for the health dimensions one table over. A row that does not say
which guiding questions it answered came out of the record's flat fields — a Notion column,
not a questionnaire — and stamping it `1` would assert that somebody was asked version 1's four
questions. There is nothing to backfill in any case: nothing has ever written this table, since
BE-07 is its first writer.

`created_by` restricts rather than setting null, which is the pair `shema_record_edits` keeps:
this is the record of who entered a reading of a team, and an account that carries one cannot
be deleted out from under it. `created_by_name` is `NOT NULL` with `''`, the same honest empty
`shema_projects.updated_by_name` took — a row whose author is unknown says so, and the
alternative is a migration asserting that somebody filed something.

No index: every read of this table is already keyed on `project_id`
(`ix_shema_health_assessments_project_date`), and nothing queries by question set version or by
author. An index for a query nobody issues costs every write and buys no read.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260911_shema04"
down_revision = "20260911_shema02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shema_health_assessments",
        sa.Column("question_set_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "shema_health_assessments",
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "shema_health_assessments",
        sa.Column("created_by_name", sa.String(200), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("shema_health_assessments", "created_by_name")
    op.drop_column("shema_health_assessments", "created_by")
    op.drop_column("shema_health_assessments", "question_set_version")
