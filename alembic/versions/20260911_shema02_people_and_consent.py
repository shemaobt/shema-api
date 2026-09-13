"""shema people: the seat's account link, consent per context, and a person's sensitive flag

Revision ID: 20260911_shema02
Revises: 20260911_shema01
Create Date: 2026-09-11

The parent is `20260911_shema01`, read with `uv run alembic heads` in this worktree on
11/sep/2026, immediately before this file was written — the measurement `docs/shema.md` §7.1
asks for rather than a value carried over from the design. BE-04 runs beside this issue on
the same base and the wave declared it first; if it lands with a migration of its own, this
one re-points at its revision, and the pull request body says so where the person merging
can see it.

Three changes, one issue:

`shema_region_teams.holder_user_id` answers the question `app/db/models/shema_org_chart.py`
left open in words — *whether a seat should also point at an account is BE-13's question*.
Nullable, `SET NULL`, and never the name: the chart stays the single source of who holds
which role where (FE-44 §5.3), and this only says which Tripod account that person signs in
with, when they have one at all.

`shema_intercessor_consents` is the first of the three privacy questions of `docs/shema.md`
§10 item 8 — *what consent was given, and how it is evidenced* — turned into a row per person
per context. **Nothing backfills it**, and that is the whole design rather than caution: an
existing row with no consent row has no consent, exactly as a NULL `prayer_visibility` is
`coordenacao` and a NULL health dimension is not `boa`. Backfilling would write a yes nobody
gave. The table is empty today because nothing has ever stored a real person.

`shema_intercessors.sensitive_country` carries `CLAUDE.md` §6.1's rule onto a person, in the
project flag's own shape. `server_default false` is the fail-closed direction here — the
inverse of the two absences above, and the same shape as media authorization, where only an
explicit `true` counts.

Written by hand like every revision in this directory: `alembic/env.py` imports only
`app.core.database`, so `--autogenerate` sees no metadata and would emit a migration dropping
every table in the schema (`docs/resource_requests.md` §8.1).

The new enum is created by `op.create_table` naming the type, as `20260911_shema01` does for
its eleven, and dropped explicitly in `downgrade` — PostgreSQL does not collect a type when
the last table using it goes, and `migrations.yml` walks the newest revision down and back up
on a real database, where a leftover type makes the second `upgrade` fail on `CREATE TYPE`.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260911_shema02"
down_revision = "20260911_shema01"
branch_labels = None
depends_on = None

CONSENT_CONTEXT = sa.Enum(
    "network",
    "directory",
    "partner-export",
    name="shema_consent_context_enum",
)


def upgrade() -> None:
    op.add_column(
        "shema_region_teams",
        sa.Column(
            "holder_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.add_column(
        "shema_intercessors",
        sa.Column(
            "sensitive_country",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "shema_intercessor_consents",
        sa.Column(
            "intercessor_id",
            sa.String(36),
            sa.ForeignKey("shema_intercessors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("context", CONSENT_CONTEXT, primary_key=True),
        sa.Column("basis", sa.String(300), nullable=False),
        sa.Column(
            "recorded_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(basis) > 0", name="ck_shema_consents_basis_present"),
    )


def downgrade() -> None:
    op.drop_table("shema_intercessor_consents")
    CONSENT_CONTEXT.drop(op.get_bind(), checkfirst=True)
    op.drop_column("shema_intercessors", "sensitive_country")
    op.drop_column("shema_region_teams", "holder_user_id")
