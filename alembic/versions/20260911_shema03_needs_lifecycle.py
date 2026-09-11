"""needs: an acknowledgement stamp, an amount that carries its currency, and the third index

Revision ID: 20260911_shema03
Revises: 20260911_shema02
Create Date: 2026-09-11

The parent is `20260911_shema02`, read with `uv run alembic heads` in this worktree
immediately before this file was written. It is BE-06's revision and the head of this
branch's own base, not of `origin/dev` — BE-07 and BE-12 branch from the same base and
author their own revisions against the same head, and the declared merge order is 07, 08,
12, so whoever the user merges second re-points. The pull request body says so;
`docs/resource_requests.md` §8.3 is why that sentence is written down rather than
remembered.

Written by hand, like every other revision here: `alembic/env.py` imports only
`app.core.database`, so its metadata is empty and `--autogenerate` would emit a migration
dropping every existing table (`docs/resource_requests.md` §8.1).

**Five columns, two constraints and two indexes, on a table BE-02 created and BE-08 owns
the behaviour of.**

`acknowledged_at`, `acknowledged_by` and `acknowledged_by_name` are the second axis: a need
that nobody has said they saw. They are nullable with **no default and no backfill** — the
rule `docs/shema.md` §7.4 states for `prayer_visibility` and for an unassessed health
dimension applies here for the same reason and with the sharpest consequence of the three: a
default would stamp every existing need as acknowledged by nobody on the day of the
migration, which is the exact failure the column exists to surface. `acknowledged_by_name`
is `''` for the same rows, and `''` is honest — no acknowledgement, no name.

`estimated_amount` and `estimated_currency` are the money pair, and the two `CHECK`s are
what make *every amount carries a currency* an invariant of the data instead of a rule of
one write path. Neither is backfilled from `estimated_value`: that column is free text a
field team typed, parsing it in a migration would be this migration deciding what somebody
meant, and a wrong number is worse than no number in the one place a donor reads.

`ix_shema_needs_urgency_status` is the third of the three axes the DoD asks for — category
and status already had one each. `ix_shema_needs_unacknowledged` is the sweep's, leading on
the column the sweep pins to NULL.

`estimated_currency` is deliberately **not** an enum: a currency list is exactly the kind a
client extends, and an enum member costs a migration (`docs/shema.md` §7.3's own test).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260911_shema03"
down_revision = "20260911_shema02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shema_needs", sa.Column("acknowledged_at", sa.Date(), nullable=True))
    op.add_column(
        "shema_needs",
        sa.Column(
            "acknowledged_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "shema_needs",
        sa.Column("acknowledged_by_name", sa.String(200), nullable=False, server_default=""),
    )

    op.add_column("shema_needs", sa.Column("estimated_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("shema_needs", sa.Column("estimated_currency", sa.String(3), nullable=True))

    op.create_check_constraint(
        "ck_shema_needs_amount_carries_currency",
        "shema_needs",
        "(estimated_amount IS NULL) = (estimated_currency IS NULL)",
    )
    op.create_check_constraint(
        "ck_shema_needs_currency_is_iso_4217",
        "shema_needs",
        "estimated_currency IS NULL OR ("
        "length(estimated_currency) = 3 AND estimated_currency = upper(estimated_currency)"
        ")",
    )

    op.create_index("ix_shema_needs_urgency_status", "shema_needs", ["urgency", "status"])
    op.create_index(
        "ix_shema_needs_unacknowledged",
        "shema_needs",
        ["acknowledged_at", "status", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_shema_needs_unacknowledged", table_name="shema_needs")
    op.drop_index("ix_shema_needs_urgency_status", table_name="shema_needs")

    op.drop_constraint("ck_shema_needs_currency_is_iso_4217", "shema_needs", type_="check")
    op.drop_constraint("ck_shema_needs_amount_carries_currency", "shema_needs", type_="check")

    op.drop_column("shema_needs", "estimated_currency")
    op.drop_column("shema_needs", "estimated_amount")
    op.drop_column("shema_needs", "acknowledged_by_name")
    op.drop_column("shema_needs", "acknowledged_by")
    op.drop_column("shema_needs", "acknowledged_at")
