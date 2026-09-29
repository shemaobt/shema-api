"""shema_request_notices: what a resource-request notice in the PME's bell points at and says

Revision ID: 20260929_shema541
Revises: 20260929_rr11
Create Date: 2026-09-29

OBT-541 (BE-21). The parent was `20260929_rr09` when this file was written (29/sep/2026); the
same day OBT-537 merged `20260929_rr10` and `rr11` into `dev`, and it was re-pointed to
`20260929_rr11`, the head `alembic heads` read after merging — a measurement, not a value to
remember (`docs/shema.md` §7.1). The id carries the issue number, as `20260927_shema524`,
`shema531` and `shema543` do, so two siblings cannot mint the same `shemaNN`.

The form's decision and arrival notices are now also written into the `shema` app, where the
PME's bell reads. `notifications` has no column for where a notice leads, and
`create_notification` does not change its signature, so each of those rows gets one detail
row here: the project it points at, and the request's registered name and stage as they were
when it was told — the only two facts of the request GATE-03 D4 lets a notice carry.

`stage` is text with a CHECK, not the form's native `rr_stage_enum`, which is the sibling
module's type to migrate. `project_id` has no `ON DELETE` action, like `rr_requests`'
own foreign key to the same table: a project with requests cannot be deleted, so neither can
it orphan their notices. The notification row takes its detail with it.

Written by hand and importing nothing from `app.`, like the other revisions: `alembic/env.py`
has empty metadata, and importing a model module builds an engine at import time.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260929_shema541"
down_revision: str | None = "20260929_rr11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shema_request_notices",
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
        sa.Column("request_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "stage IN ('triagem', 'aprovado', 'condicional', 'revisar', 'recusado')",
            name="ck_shema_request_notices_stage",
        ),
    )


def downgrade() -> None:
    op.drop_table("shema_request_notices")
