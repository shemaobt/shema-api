"""whoever registers gets in: resource-request-form approves access requests itself

Revision ID: 20260828_rr02
Revises: 20260825_rr01
Create Date: 2026-08-28

GATE-02 D1 (OBT-448, 27/aug/2026) asked how a team gets access and the client answered
*"quem tiver uma conta"*. That is `apps.auto_approve`, which
`create_access_request` already honours and which
`access_request/_default_roles.py` already pairs with `equipe`, the least privileged of
this app's three roles. Everything for the answer existed except the value.

**A data revision and not a line in `scripts/seed_apps_roles.py`**, because the row it has
to reach already exists. BE-00 seeded it, the seed script is run by hand, and it only
backfills `app_url` when that column is empty — nothing in it would ever revisit a boolean
on a row already written. A revision is the one path that runs against production without
somebody remembering to run it. `20260518_0001` writes the same column the same way, for
`project-health`.

The `WHERE` names the app key rather than an id: ids are per-installation uuids and the key
is the same everywhere, which is what makes this safe to run on a database where the row
was never seeded at all — it updates nothing and the deploy carries on.

The key is spelled here rather than imported from `app.api.resource_requests._deps`, which
is where the module names it once. Importing anything under `app.` executes
`app.core.database` and builds an engine at import time, so an unrelated import error would
fail the deploy's migration step before a statement runs — the reasoning `20260731_0001`
recorded and `20260825_rr01` repeated for its DDL. A revision is also a permanent record of
what ran on this date, and should keep running exactly that.

Reversible, and the downgrade is not decoration: turning this off is how an installation
closes public registration again, and `false` is the column's own default, so down leaves
the row exactly as `20260517_0001` created it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_rr02"
down_revision: str | None = "20260825_rr01"
branch_labels = None
depends_on = None

APP_KEY = "resource-request-form"


def _set_auto_approve(value: bool) -> None:
    op.execute(
        sa.text("UPDATE apps SET auto_approve = :value WHERE app_key = :app_key").bindparams(
            value=value, app_key=APP_KEY
        )
    )


def upgrade() -> None:
    _set_auto_approve(True)


def downgrade() -> None:
    _set_auto_approve(False)
