"""shema_project_notices: what a project notice in the PME's bell says, as facts

Revision ID: 20261002_shema559
Revises: 20261001_shema552
Create Date: 2026-10-02

OBT-559. The parent is `20261001_shema552`, read with `uv run alembic heads` in this worktree on
2/out/2026 immediately before this file was written — a measurement, not a value to remember
(`docs/shema.md` §7.1). OBT-560 (shema-api#610) writes `20261002_shema560` on the same parent; the
one of the two that lands second is re-pointed at the other. The id carries the issue number, as
`20260929_shema541` does, so two siblings cannot mint the same `shemaNN`.

The four project notices — a health reading turned critical, urgent needs, a Pulse and its prayer
request — were written as English prose into `notifications.title` and `body`, and the bell showed
that prose as it came: in English, and, for an urgent need, with the place it was written with,
to whoever reads the row later (OBT-556, item 1). The console now writes the sentence in the
reader's language from facts, and each of those rows gets one detail row here: the project it is
about, and what happened — the day, the needs, who sent the Pulse. The name, the region and the
place are read off the project when the panel is read, so no column here can hold them.

`notifications` keeps its shape; it is shared with every other app. `project_id` has no `ON
DELETE` action, like `shema_request_notices`' own: a project is marked, never deleted. The
notification row takes its detail with it.

Written by hand and importing nothing from `app.`, like the other revisions: `alembic/env.py`
has empty metadata, and importing a model module builds an engine at import time.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20261002_shema559"
down_revision: str | None = "20261001_shema552"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shema_project_notices",
        sa.Column(
            "notification_id",
            sa.String(36),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id"),
            nullable=False,
        ),
        sa.Column("assessed_on", sa.Date(), nullable=True),
        sa.Column("need_count", sa.Integer(), nullable=True),
        sa.Column("need_categories", sa.JSON(), nullable=True),
        sa.Column("need_totals", sa.JSON(), nullable=True),
        sa.Column("submitted_by", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("shema_project_notices")
