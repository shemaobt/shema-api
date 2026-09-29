"""the team's instance: who started it, when it was cancelled, one open per project

Revision ID: 20260929_rr09
Revises: 20260928_rr08
Create Date: 2026-09-29

BE-25 (OBT-534), on GATE-04 D2 and D6 (OBT-519, Daniel, 23/sep/2026): a request is an instance
of a project's team, started by one member who alone writes it until it is submitted or
cancelled, and a project has one open instance at a time.

1. ``rr_requests.started_by``, a nullable FK to ``users`` — who holds the pen. Backfilled from
   ``created_by``, because every existing row was opened by a person and that person is the
   one who wrote it. Nullable for the request a link opens (BE-26, OBT-537).
2. ``rr_requests.cancelled_at`` — giving an instance up marks it, it never deletes it.
3. ``uq_rr_requests_one_open_per_project``, a unique index on ``shema_project_id`` over the
   rows that are neither submitted nor cancelled. Rows with no project are outside it by
   construction — ``NULL`` is never equal to ``NULL`` in a unique index — which is the board's
   door and the link's until OBT-547 registers the project.

**No existing row can collide with the index**: ``shema_project_id`` was born in
``20260928_rr08`` a day ago, nullable and backfilled with nothing, so every row it could count
is ``NULL``. Should that stop being true on some environment, the index creation fails loud
here, which is the right place to learn it.

Written by hand and importing nothing from ``app.``, like every rr revision.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260929_rr09"
down_revision: str | None = "20260928_rr08"
branch_labels = None
depends_on = None

OPEN = "submitted_at IS NULL AND cancelled_at IS NULL"


def upgrade() -> None:
    op.add_column(
        "rr_requests",
        sa.Column("started_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("rr_requests", sa.Column("cancelled_at", sa.DateTime(timezone=True)))

    op.execute(sa.text("UPDATE rr_requests SET started_by = created_by WHERE started_by IS NULL"))

    op.create_index(
        "uq_rr_requests_one_open_per_project",
        "rr_requests",
        ["shema_project_id"],
        unique=True,
        postgresql_where=sa.text(OPEN),
        sqlite_where=sa.text(OPEN),
    )


def downgrade() -> None:
    op.drop_index("uq_rr_requests_one_open_per_project", table_name="rr_requests")
    op.drop_column("rr_requests", "cancelled_at")
    op.drop_column("rr_requests", "started_by")
