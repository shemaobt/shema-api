"""shema_project_members: the account ↔ project link that says who a project's team is

Revision ID: 20260927_shema524
Revises: 20260927_shema08
Create Date: 2026-09-27

OBT-524 (BE-18 of the PME). The parent is `20260927_shema08`, read with `uv run alembic heads`
in this worktree on 27/sep/2026, after merging OBT-523's branch and immediately before this file
was written — a measurement, not a value to remember (`docs/resource_requests.md` §8.3). The id
carries the issue number rather than the next `shemaNN`, as OBT-531's does: the counter has
collided once already, and OBT-524, OBT-543 and OBT-528 all hang off `shema08`. The declared
merge order is 523 → 524 → 543 → 527 → 531 → 399 → 400, so OBT-543 re-points onto this one.

**Removal marks, it never deletes** — `removed_at` and `removed_by` — and the partial unique
index is what turns *one live membership per account and project* into a rule about live rows
only: history accumulates under the same pair while the present stays single. `postgresql_where`
alone carries it here because migrations only ever run on PostgreSQL (`docs/shema.md` §7.2); the
SQLite half of the same index lives on the model, where `create_all` builds the suite's schema.
`app/db/models/shema_project_member.py` carries the argument for every column and foreign key.

Written by hand like the other revisions: `alembic/env.py` has empty metadata and
`--autogenerate` would drop every existing table.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_shema524"
down_revision: str | None = "20260927_shema08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shema_project_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "added_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "removed_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("role IN ('equipe')", name="ck_shema_project_members_role"),
    )
    op.create_index(
        "uq_shema_project_members_live",
        "shema_project_members",
        ["project_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("removed_at IS NULL"),
    )
    op.create_index("ix_shema_project_members_user", "shema_project_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_shema_project_members_user", table_name="shema_project_members")
    op.drop_index("uq_shema_project_members_live", table_name="shema_project_members")
    op.drop_table("shema_project_members")
