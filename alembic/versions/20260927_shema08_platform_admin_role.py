"""the Admin of OBT-522: one `admin` role in the shema app and in the resource-request form

Revision ID: 20260927_shema08
Revises: 20260917_0001
Create Date: 2026-09-27

The parent is `20260917_0001`, read with `uv run alembic heads` in this worktree on
27/sep/2026, immediately before this file was written — a measurement, not a value to
remember (`docs/resource_requests.md` §8.3). OBT-524, OBT-543 and OBT-528 stack on this
branch and hang their own revisions off this one; whichever of two siblings the user merges
second re-points its `down_revision`.

**A data revision.** OBT-522 (Daniel, 23 and 25/sep) made the Admin one role for both apps,
shown as *"Admin da plataforma"*; it is not `users.is_platform_admin`. Nobody is granted it
here — OBT-543 grants it. The role row is written in both apps because each app's guards
read their own grants.

**Skip, insert or relabel, per app.** An app this installation never registered is skipped:
`scripts/seed_apps_roles.py` creates the app and writes the same role with the same label
when it does (`tests/test_shema/test_admin_role.py` holds the two to each other). A missing
role is inserted; a role already there under another label is relabelled, so the label is
the same on every installation.

**The downgrade takes the role out of both apps, and what hangs off it goes with it** —
`user_app_roles`, `access_invites` and `role_permissions` all reference `roles.id` with
`ON DELETE CASCADE`. Undoing the role is undoing every grant of it; there is nothing else
the downgrade could mean.

The keys and the label are written here rather than imported: importing anything under
`app.` builds an engine at import time (the argument `20260828_rr02` records), and a revision
is the record of what ran on this date.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20260927_shema08"
down_revision: str | None = "20260917_0001"
branch_labels = None
depends_on = None

ROLE_KEY = "admin"
LABEL = "Admin da plataforma"
APP_KEYS = ("resource-request-form", "shema")


def _app_id(bind: Connection, app_key: str) -> str | None:
    return bind.execute(
        sa.text("SELECT id FROM apps WHERE app_key = :app_key"), {"app_key": app_key}
    ).scalar()


def seed_admin_role(bind: Connection) -> None:
    """Give each registered app of :data:`APP_KEYS` the role, under :data:`LABEL`."""
    for app_key in APP_KEYS:
        app_id = _app_id(bind, app_key)
        if app_id is None:
            continue
        params = {"app_id": app_id, "role_key": ROLE_KEY, "label": LABEL, "is_system": True}
        exists = bind.execute(
            sa.text("SELECT id FROM roles WHERE app_id = :app_id AND role_key = :role_key"),
            params,
        ).scalar()
        if exists is None:
            bind.execute(
                sa.text(
                    "INSERT INTO roles (id, app_id, role_key, label, is_system) "
                    "VALUES (:id, :app_id, :role_key, :label, :is_system)"
                ),
                {**params, "id": str(uuid.uuid4())},
            )
        else:
            bind.execute(
                sa.text(
                    "UPDATE roles SET label = :label, is_system = :is_system "
                    "WHERE app_id = :app_id AND role_key = :role_key"
                ),
                params,
            )


def drop_admin_role(bind: Connection) -> None:
    """Take the role out of both apps; the foreign keys take its grants and invites."""
    for app_key in APP_KEYS:
        app_id = _app_id(bind, app_key)
        if app_id is None:
            continue
        bind.execute(
            sa.text("DELETE FROM roles WHERE app_id = :app_id AND role_key = :role_key"),
            {"app_id": app_id, "role_key": ROLE_KEY},
        )


def upgrade() -> None:
    seed_admin_role(op.get_bind())


def downgrade() -> None:
    drop_admin_role(op.get_bind())
