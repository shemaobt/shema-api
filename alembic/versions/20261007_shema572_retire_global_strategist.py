"""the Global Strategist leaves: its grants and pending invites are revoked

Revision ID: 20261007_shema572
Revises: 20261006_shema567
Create Date: 2026-10-07

The parent is `20261006_shema567`, read with `uv run alembic heads` in this worktree on
7/oct/2026, immediately before this file was written — a measurement, not a value to remember
(`docs/shema.md` §7.1).

**A data revision.** Karina (via Daniel, 6/oct/2026) had meant to retire the *Estrategista
Global* and keep *Coordenador / Administrador Regional / Resource Circle*; Daniel decided on
7/oct that the accounts holding the role **lose it** — they are not converted to coordinator,
and the Admin grants another role to whoever needs one (OBT-572). The key leaves
`app/services/shema/_scope.py`'s catalogue in the same change, so the seed stops writing the row
and the PME's surface stops granting it; this is the half that reaches installations that already
hold grants.

**Guarded by the value, in both directions.** The upgrade revokes every **live** grant of the
role in the `shema` app and every **pending** invite for it (not accepted, not revoked, not
expired), and stamps both with :data:`MARK` — a fixed instant rather than `now()`, so the rows
this revision touched are the rows carrying exactly that stamp. The downgrade clears the stamp
from those rows and no others: a grant somebody revoked by hand before or after this ran keeps
its own `revoked_at`, and a grant nobody ever had is not invented. The `roles` row itself is left
alone — `user_app_roles`, `access_invites` and `role_permissions` point at it with
`ON DELETE CASCADE`, so deleting it would erase the very history this revision is careful to
keep, and nothing re-seeds it.

**Who was affected is listed before this runs, never discovered by it**: the read-only query
(`OBT-572`, delivered to Daniel before the deploy) names the accounts, so the Admin can grant
another role to whoever needs one and nobody loses access without knowing.

The keys are written here rather than imported: importing anything under `app.` builds an engine
at import time (the argument `20260828_rr02` records), and a revision is the record of what ran
on this date.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20261007_shema572"
down_revision: str | None = "20261006_shema567"
branch_labels = None
depends_on = None

APP_KEY = "shema"
ROLE_KEY = "globalStrategist"
#: The instant written on every row this revision revokes — the downgrade's handle on them. A
#: ``datetime`` and not its ISO string: the env runs on asyncpg, which types the parameter as
#: ``timestamptz`` and refuses a ``str`` even with no row to update.
MARK = datetime(2026, 10, 7, tzinfo=UTC)

_ROLE_IDS = (
    "SELECT roles.id FROM roles JOIN apps ON apps.id = roles.app_id "
    "WHERE apps.app_key = :app_key AND roles.role_key = :role_key"
)


def _stamped(sql: str) -> sa.TextClause:
    """``sql`` with the three parameters bound, ``mark`` typed so each dialect renders it."""
    return sa.text(sql).bindparams(
        sa.bindparam("app_key", APP_KEY),
        sa.bindparam("role_key", ROLE_KEY),
        sa.bindparam("mark", MARK, type_=sa.DateTime(timezone=True)),
    )


def revoke_global_strategist(bind: Connection) -> tuple[int, int]:
    """Revoke the live grants and the pending invites of the role, stamped with :data:`MARK`.

    Returns ``(grants, invites)`` — how many of each this run revoked.
    """
    grants = bind.execute(
        _stamped(
            "UPDATE user_app_roles SET revoked_at = :mark "
            f"WHERE revoked_at IS NULL AND role_id IN ({_ROLE_IDS})"
        )
    ).rowcount
    invites = bind.execute(
        _stamped(
            "UPDATE access_invites SET revoked_at = :mark "
            "WHERE revoked_at IS NULL AND accepted_at IS NULL "
            f"AND expires_at > CURRENT_TIMESTAMP AND role_id IN ({_ROLE_IDS})"
        )
    ).rowcount
    return grants, invites


def restore_global_strategist(bind: Connection) -> tuple[int, int]:
    """Clear :data:`MARK` from the rows the upgrade stamped — those and no others."""
    grants = bind.execute(
        _stamped(
            "UPDATE user_app_roles SET revoked_at = NULL "
            f"WHERE revoked_at = :mark AND role_id IN ({_ROLE_IDS})"
        )
    ).rowcount
    invites = bind.execute(
        _stamped(
            "UPDATE access_invites SET revoked_at = NULL "
            f"WHERE revoked_at = :mark AND role_id IN ({_ROLE_IDS})"
        )
    ).rowcount
    return grants, invites


def upgrade() -> None:
    revoke_global_strategist(op.get_bind())


def downgrade() -> None:
    restore_global_strategist(op.get_bind())
