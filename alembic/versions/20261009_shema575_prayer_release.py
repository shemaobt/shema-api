"""a sensitive project's prayer request waits for the coordination before the wall and the Pulse

Revision ID: 20261009_shema575
Revises: 20261008_shema578
Create Date: 2026-10-09

OBT-575 — Karina, via Daniel, 6/oct/2026: *"A coordenação revisa o texto antes de ele ir ao
mural e ao Pulso."* A request the team authorized on a sensitive project leaves only once the
coordination has released it, and the coordination may edit the text it releases. Both rows
that hold a request gain the same pair: ``shema_projects`` for the project's own request and
``shema_needs`` for each shared need. ``*_released_from`` is the team's text the release was
given for and ``*_released_text`` is what leaves in its place; a team that writes a new text
is no longer released, with nothing to clear.

Both nullable with no default: NULL is *never released*, and a backfill would release every
sensitive request in the database unread.

The parent is `20261008_shema578`, read with `uv run alembic heads` in this worktree on
9/oct/2026, immediately before this file was written. Written by hand and importing nothing from
``app.``, like every revision here.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20261009_shema575"
down_revision: str | None = "20261008_shema578"
branch_labels = None
depends_on = None

TABLES = ("shema_projects", "shema_needs")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("prayer_released_from", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("prayer_released_text", sa.Text(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "prayer_released_text")
        op.drop_column(table, "prayer_released_from")
