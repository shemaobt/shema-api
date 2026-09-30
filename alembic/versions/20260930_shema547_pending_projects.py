"""pending projects: the mesa's approval files a project the Admin confirms or discards

Revision ID: 20260930_shema547
Revises: 20260929_shema541
Create Date: 2026-09-30

OBT-547 (BE-23 of the PME). The parent is `20260929_shema541`, read with `uv run alembic heads`
in this worktree on 30/sep/2026 immediately before this file was written — a measurement, not a
value to remember (`docs/shema.md` §7.1). The id carries the issue number, as `shema524`,
`shema531`, `shema543` and `shema541` do.

Three changes, one per table:

- `shema_projects` gains the pending state: `pending_confirmation`, the request and the link that
  filed the project, and the discard's who, when and why. Two unique indexes carry the
  idempotency — one project per request, one live project per link among those not discarded —
  and the second is partial, `postgresql_where` here and both halves on the model, where
  `create_all` builds the suite's schema (`docs/shema.md` §7.2). The two sources are **not**
  foreign keys: `rr_requests.shema_project_id` points back, and a pair that named each other
  could be deleted in no order.
- `shema_project_pending_members` is the list a pending project proposes — the form's team
  table and the link's own address.
- `access_invites` gains `project_id`, and `role_id` becomes nullable under a CHECK that asks for
  one of the two: an invitation to a project's team grants no role (OBT-524).

**The downgrade refuses rather than erases**, as `20260929_rr11`'s does: a project filed by an
approval, or an invitation to a team, has no shape to go back to, and dropping the columns would
delete them silently.

Written by hand and importing nothing from `app.`, like the other revisions: `alembic/env.py`
has empty metadata, and importing a model module builds an engine at import time.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260930_shema547"
down_revision: str | None = "20260929_shema541"
branch_labels = None
depends_on = None

PROJECTS = "shema_projects"
INVITES = "access_invites"
DISCARDED_BY_FK = "fk_shema_projects_discarded_by"
INVITE_PROJECT_FK = "fk_access_invites_project_id"
ROLE_OR_PROJECT = "ck_access_invites_role_or_project"


def upgrade() -> None:
    op.add_column(
        PROJECTS,
        sa.Column(
            "pending_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(PROJECTS, sa.Column("source_request_id", sa.String(36), nullable=True))
    op.add_column(PROJECTS, sa.Column("source_link_id", sa.String(36), nullable=True))
    op.add_column(PROJECTS, sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(PROJECTS, sa.Column("discarded_by", sa.String(36), nullable=True))
    op.add_column(PROJECTS, sa.Column("discard_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        DISCARDED_BY_FK, PROJECTS, "users", ["discarded_by"], ["id"], ondelete="SET NULL"
    )
    op.create_index(
        "uq_shema_projects_source_request", PROJECTS, ["source_request_id"], unique=True
    )
    op.create_index(
        "uq_shema_projects_live_source_link",
        PROJECTS,
        ["source_link_id"],
        unique=True,
        postgresql_where=sa.text("discarded_at IS NULL"),
    )

    op.create_table(
        "shema_project_pending_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("role", sa.Text(), nullable=False, server_default=""),
        sa.Column("email", sa.String(320), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_shema_project_pending_members_project_id",
        "shema_project_pending_members",
        ["project_id"],
    )

    op.add_column(INVITES, sa.Column("project_id", sa.String(120), nullable=True))
    op.create_foreign_key(
        INVITE_PROJECT_FK, INVITES, PROJECTS, ["project_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_access_invites_project_id", INVITES, ["project_id"])
    op.alter_column(INVITES, "role_id", existing_type=sa.String(36), nullable=True)
    op.create_check_constraint(ROLE_OR_PROJECT, INVITES, "role_id IS NOT NULL OR project_id IS NOT NULL")


def downgrade() -> None:
    bind = op.get_bind()
    team_invites = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {INVITES} WHERE role_id IS NULL")
    ).scalar_one()
    filed = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {PROJECTS} WHERE source_request_id IS NOT NULL")
    ).scalar_one()
    if team_invites or filed:
        raise RuntimeError(
            f"{filed} projects were filed by an approval and {team_invites} invitations are to a "
            "project's team; downgrading would have to erase them."
        )

    op.drop_constraint(ROLE_OR_PROJECT, INVITES, type_="check")
    op.alter_column(INVITES, "role_id", existing_type=sa.String(36), nullable=False)
    op.drop_index("ix_access_invites_project_id", table_name=INVITES)
    op.drop_constraint(INVITE_PROJECT_FK, INVITES, type_="foreignkey")
    op.drop_column(INVITES, "project_id")

    op.drop_index(
        "ix_shema_project_pending_members_project_id", table_name="shema_project_pending_members"
    )
    op.drop_table("shema_project_pending_members")

    op.drop_index("uq_shema_projects_live_source_link", table_name=PROJECTS)
    op.drop_index("uq_shema_projects_source_request", table_name=PROJECTS)
    op.drop_constraint(DISCARDED_BY_FK, PROJECTS, type_="foreignkey")
    for column in (
        "discard_reason",
        "discarded_by",
        "discarded_at",
        "source_link_id",
        "source_request_id",
        "pending_confirmation",
    ):
        op.drop_column(PROJECTS, column)
