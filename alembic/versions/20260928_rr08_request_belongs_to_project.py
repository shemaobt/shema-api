"""a request belongs to a PME project, and the team stops being a grant of this app

Revision ID: 20260928_rr08
Revises: 20260927_shema_eten01
Create Date: 2026-09-28

GATE-04 (OBT-519) and the access model of 22 and 25/sep/2026 (OBT-522) moved the team out of
this app: **a team is the members of a project in the PME** (``shema_project_members``,
OBT-524), and nobody registers for the form any more — it has no login. BE-19 (OBT-520) is
the server half, and this revision is its schema and data:

1. ``rr_requests.shema_project_id``, a nullable FK to ``shema_projects`` with an index. Written
   at creation for a member and at the mesa's approval for a request that entered by the
   Admin's link (OBT-547); nullable for that second door. ``String(120)`` because the PME's
   project id is the export's slug, not a uuid (FE-44 §5.1).
2. **Every live ``equipe`` grant of this app is revoked** — ``revoked_at`` written, the row
   kept. The team holds ``equipe`` through a membership now (``_membership.py``), so a grant
   would be a second door into the same room, and the one nobody administers.
3. **``auto_approve`` goes back to false** — the value ``20260828_rr02`` wrote for GATE-02 D1
   and whose own docstring said this day would come (*"sim por enquanto"*, 28/aug/2026).

**Two things GATE-04 D5 asks that this revision deliberately does not do**, each recorded
rather than silently skipped:

* **The ``equipe`` role row stays.** It is a key of the capability table the frontend emits
  (``capabilities.json``) and of ``scripts/seed_apps_roles.py``'s override, both pinned by
  tests; deleting the row would be re-created by the next seed run. With every grant revoked
  and registration closed, only an Admin reviewing an access request hands it out again
  (``_default_roles.py`` keeps the entry for the platform's approvability guard). ``lider`` stays too, and for a sharper reason: the base leader endorses by link
  only once OBT-535 exists, and removing the role first would stop every endorsement.
* **The existing requests are not deleted here.** Four tables of this module are append-only
  under ``rr_reject_write()`` (``20260825_rr01``), the ledger among them, so deleting the
  test requests means lifting that guard inside a migration and erasing ledger movements and
  audit trails that ran on every environment this deploys to. That is its own, explicitly
  reviewed step, not a side effect of adding a column.

Written by hand and importing nothing from ``app.``, like every rr revision: importing a model
module executes ``app.core.database``, which builds an engine at import time. The app key is
spelled here for the same reason ``20260828_rr02`` spells it.

The downgrade drops the column and turns ``auto_approve`` back on; **it does not restore the
revoked grants** — which accounts held them is still in the rows, but re-granting access on a
downgrade is a decision, not an undo.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260928_rr08"
down_revision: str | None = "20260927_shema_eten01"
branch_labels = None
depends_on = None

APP_KEY = "resource-request-form"
TEAM_ROLE = "equipe"


def upgrade() -> None:
    op.add_column(
        "rr_requests",
        sa.Column(
            "shema_project_id",
            sa.String(120),
            sa.ForeignKey("shema_projects.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_rr_requests_shema_project_id", "rr_requests", ["shema_project_id"])

    op.execute(
        sa.text(
            "UPDATE user_app_roles SET revoked_at = CURRENT_TIMESTAMP "
            "WHERE revoked_at IS NULL AND role_id IN ("
            "  SELECT roles.id FROM roles JOIN apps ON apps.id = roles.app_id "
            "  WHERE apps.app_key = :app_key AND roles.role_key = :role_key"
            ")"
        ).bindparams(app_key=APP_KEY, role_key=TEAM_ROLE)
    )
    op.execute(
        sa.text("UPDATE apps SET auto_approve = :value WHERE app_key = :app_key").bindparams(
            value=False, app_key=APP_KEY
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE apps SET auto_approve = :value WHERE app_key = :app_key").bindparams(
            value=True, app_key=APP_KEY
        )
    )
    op.drop_index("ix_rr_requests_shema_project_id", table_name="rr_requests")
    op.drop_column("rr_requests", "shema_project_id")
