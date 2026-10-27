"""sensitive countries: the list Karina approved, which the write path reads and the Admin edits

Revision ID: 20261027_shema616
Revises: 20261009_shema575
Create Date: 2026-10-27

OBT-616. The parent is `20261009_shema575`, read with `uv run alembic heads` in this worktree on
27/out/2026 immediately before this file was written — a measurement, not a value to remember
(`docs/shema.md` §7.1).

One table, `shema_sensitive_countries`: a country as the list names it, and the other spellings a
`location` may write it in. It is seeded with the list Karina approved on 19/out/2026 — India,
China, Iran, Iraq, the Middle East, and Egypt, Turkey and Cyprus — each under her Portuguese name,
with its English name and the variants a team may type (Portugal's Portuguese, Spanish). From
here on the list is the Admin's, edited in the console; this revision is only where it starts.

**It writes no project.** Daniel, 19/out/2026: the rule holds for the projects created or saved
from now on, with no migration and no retroactive check — so nothing here reads or touches
`shema_projects`, and `tests/test_shema616_migration.py` walks this revision over a stored project
in a listed country and finds it as it was, up and down.

`op.bulk_insert` and not a raw `INSERT`: the spellings are a JSON array, and the migration test
walks this one revision on SQLite (`docs/shema.md` §7.2), where a `CAST(… AS JSON)` means nothing.
Written by hand and importing nothing from `app.`, like the other revisions.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20261027_shema616"
down_revision: str | None = "20261009_shema575"
branch_labels = None
depends_on = None

#: Karina's list, 19/out/2026, in her order: the four she named, the Middle East, and the three
#: she approved as debatable. The name is hers; the spellings are what a place may also say.
KARINAS_LIST: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Índia", ("India",)),
    ("China", ()),
    ("Irã", ("Iran", "Irão")),
    ("Iraque", ("Iraq", "Irak")),
    ("Arábia Saudita", ("Saudi Arabia",)),
    ("Bahrein", ("Bahrain", "Barém", "Baréin")),
    ("Catar", ("Qatar",)),
    ("Emirados Árabes Unidos", ("United Arab Emirates", "UAE", "Emiratos Árabes Unidos")),
    ("Iêmen", ("Yemen", "Iémen")),
    ("Israel", ()),
    ("Jordânia", ("Jordan",)),
    ("Kuwait", ("Koweit", "Kuweit")),
    ("Líbano", ("Lebanon",)),
    ("Omã", ("Oman",)),
    ("Palestina", ("Palestine",)),
    ("Síria", ("Syria",)),
    ("Egito", ("Egypt",)),
    ("Turquia", ("Turkey", "Türkiye")),
    ("Chipre", ("Cyprus",)),
)


def upgrade() -> None:
    table = op.create_table(
        "shema_sensitive_countries",
        sa.Column("name", sa.String(120), primary_key=True),
        sa.Column("spellings", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.bulk_insert(
        table,
        [{"name": name, "spellings": list(spellings)} for name, spellings in KARINAS_LIST],
    )


def downgrade() -> None:
    op.drop_table("shema_sensitive_countries")
