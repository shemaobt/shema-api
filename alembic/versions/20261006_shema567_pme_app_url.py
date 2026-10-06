"""the PME's app_url is the address it answers on

Revision ID: 20261006_shema567
Revises: 20261004_meet02
Create Date: 2026-10-06

The parent is `20261004_meet02`, read with `uv run alembic heads` in this worktree on
6/oct/2026, immediately before this file was written — a measurement, not a value to remember
(`docs/shema.md` §7.1).

**A data revision, one row.** BE-03 seeded the `shema` app (the PME) with
`https://shema.shemaywam.com`, a conventional hostname chosen because there was no deployment
to read; it never got a DNS record, and `request_password_reset` builds the reset e-mail as
`{app_url}/reset-password?token=…`, so the PME's password recovery led to a host that does not
exist (OBT-567). The user decided on 6/oct/2026 that the PME's address is the Cloud Run one in
use, and that no `shema.shemaywam.com` is planned. `scripts/seed_apps_roles.py` now carries that
address for a fresh installation; this is the UPDATE for one that already holds the row, since
the seed fills only an empty `app_url`.

**Guarded by the old value.** The `WHERE` names the retired hostname as well as the app key, so
a row somebody already corrected by hand — staging is the likely case — is left exactly as they
left it. An installation without the `shema` row is untouched too: the seed writes the right
value when it registers the app.

**The downgrade does not put the old hostname back.** A host with no DNS record is not a state
worth returning to, and the forward step is itself idempotent — running it again on a corrected
row matches nothing. `migrations.yml` walks this revision down and up on a clean Postgres, where
the apps table is empty and both directions are no-ops, which is the same shape
`20261004_meet02` already has there.

The two URLs are written here rather than imported from the seed: importing anything under
`app.` or `scripts.` builds an engine at import time (the argument `20260828_rr02` records), and
a revision is the record of what ran on this date. `tests/test_shema/test_pme_app_url.py` holds
them to the seed.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "20261006_shema567"
down_revision: str | None = "20261004_meet02"
branch_labels = None
depends_on = None

APP_KEY = "shema"
OLD_URL = "https://shema.shemaywam.com"
NEW_URL = "https://project-management-ecosystem-f7ssqjozfq-uc.a.run.app"


def point_pme_at_its_address(bind: Connection) -> int:
    """Rewrite the `shema` row's `app_url` from :data:`OLD_URL` to :data:`NEW_URL`.

    Returns how many rows changed — one when the installation still held the retired hostname,
    zero when the row was already corrected or was never registered.
    """
    result = bind.execute(
        sa.text(
            "UPDATE apps SET app_url = :new_url "
            "WHERE app_key = :app_key AND app_url = :old_url"
        ),
        {"app_key": APP_KEY, "old_url": OLD_URL, "new_url": NEW_URL},
    )
    return result.rowcount


def upgrade() -> None:
    point_pme_at_its_address(op.get_bind())


def downgrade() -> None:
    """Nothing to undo: a hostname with no DNS record is not a state worth returning to."""
