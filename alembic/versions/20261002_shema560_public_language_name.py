"""a sensitive project's language gets a public name, for everyone but coordination

Revision ID: 20261002_shema560
Revises: 20261001_shema552
Create Date: 2026-10-02

OBT-560, the residue of the INT-12 privacy pass that OBT-552 left: the language's name can name
the place (*Sa'di of High Egypt*), and it left the server for every reader. Karina, via Daniel,
1/out/2026, chose a name coordination registers for those projects. One nullable column, because
``None`` is a state of its own — *nobody registered one yet* — and the boundary reads it as such,
showing the region key in its place.

The parent is ``20261001_shema552``, read with ``uv run alembic heads`` in this worktree on
2/out/2026 immediately before this file was written. Written by hand and importing nothing from
``app.``, like the other revisions.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20261002_shema560"
down_revision: str | None = "20261001_shema552"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shema_projects", sa.Column("public_language_name", sa.String(200), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("shema_projects", "public_language_name")
