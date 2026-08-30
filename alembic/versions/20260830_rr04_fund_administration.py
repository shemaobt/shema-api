"""funds stop being seeded and start being created: retirement, unique names, one real row

Revision ID: 20260830_rr04
Revises: 20260830_rr03
Create Date: 2026-08-30

GATE-01 D1 left four of PRD v1.1 §3's names undecided and the client asked for *"talvez
uma área que pudesse ser editável dos fundos"*. That area is the real answer to "decide
later" — the client types instead of us guessing — and BE-10 (OBT-471) builds it. What
this revision does is give ``rr_funds`` what a table with a life cycle has and it did not.

**``provisional`` is dropped.** It said *the gate has not confirmed this name*; the gate
closed, and the choice it was holding open stopped existing the moment the client answered
that the Gestor names the funds himself. Nothing ever read it — the model defined it, the
seed wrote ``False`` into it, and no query honoured it — so the honest move was to remove
it rather than invent a reader. The column is not recreated on the way down as ``true``
either: every row that outlives this revision was confirmed by the person who typed it,
which is what ``server_default false`` says in ``downgrade``.

**``retired_at`` is the flag it never had.** A fund the ledger cites can never be deleted —
``rr_fund_movements`` holds a foreign key and the ledger is append-only — so ending a fund
is hiding it from the list of choice, not removing it from the past. A timestamp instead of
a boolean because *when it stopped* is what a movement from last year raises and a boolean
cannot answer. Null is the state of every fund that ever existed before this ran, which is
why it needs no backfill.

**``name`` becomes ``UNIQUE``.** The id is opaque and never shown (``uuid4().hex``, minted
by the server), so the name is the fund's only human identity on the screen that assigns
money. The constraint spans retired rows on purpose: a name in the ledger's history still
names that money, and letting a new fund take it would make one history read as two.

**Shema Línguas is written here as a real row**, with the id ``linguas`` it already has —
the vendored emission carries that id, the seed's ten cards write ``fund_id = "linguas"``,
and minting a uuid for it would make three places disagree. It is an ``INSERT`` guarded by
``NOT EXISTS`` rather than a bare one because the seed script has been writing this row
since ``20260825_rr01``, so a database that has been seeded already has it. From here the
script no longer writes it: fund rows are created, and the one the client confirmed is
created by this migration.

Written by hand like the other revisions here, and importing nothing from ``app.``:
importing a model module executes ``app.core.database``, which builds an engine at import
time — the reasoning 20260731_0001 recorded and every rr revision repeats.

⚠️ One-head discipline: BE-14 and BE-15 create migrations on this same line. Whichever
merges second re-parents its ``down_revision`` or writes the merge revision —
``uv run alembic heads`` before opening the PR is the check.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260830_rr04"
down_revision = "20260830_rr03"
branch_labels = None
depends_on = None

CONFIRMED_FUND = ("linguas", "Shema Línguas")


def upgrade() -> None:
    op.add_column("rr_funds", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_rr_funds_name", "rr_funds", ["name"])
    op.drop_column("rr_funds", "provisional")

    fund_id, name = CONFIRMED_FUND
    op.execute(
        sa.text(
            "INSERT INTO rr_funds (id, name) SELECT :id, :name "
            "WHERE NOT EXISTS (SELECT 1 FROM rr_funds WHERE id = :id)"
        ).bindparams(id=fund_id, name=name)
    )


def downgrade() -> None:
    op.add_column(
        "rr_funds",
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.drop_constraint("uq_rr_funds_name", "rr_funds", type_="unique")
    op.drop_column("rr_funds", "retired_at")
