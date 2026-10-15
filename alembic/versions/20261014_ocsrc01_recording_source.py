"""oc_recordings carries where it came from: source and source_reference

Revision ID: 20261014_ocsrc01
Revises: 20261014_scene05
Create Date: 2026-10-14

One mark on the recording for the provenance of the audio and of everything attached to
it: the classification, the title, the storyteller it points at. ``source`` is ``raw`` for
what the team captures in the app and ``external`` for what an importer brings in from a
published source; ``source_reference`` is the citation in the second case.

The server default is what makes the add safe without a backfill: every row that exists
today was written by the app, so ``raw`` is the true value for all of them, and Postgres
stores the default in the catalog without rewriting the table. There is no CHECK
constraint, for the reason ``ProjectRole`` gives in ``app.core.enums``: the accepted
values are enforced at the write path, and a constraint would have to be reconciled with
production rows blind.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_ocsrc01"
down_revision: str | None = "20261014_scene05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "oc_recordings",
        sa.Column("source", sa.String(20), nullable=False, server_default="raw"),
    )
    op.add_column("oc_recordings", sa.Column("source_reference", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("oc_recordings", "source_reference")
    op.drop_column("oc_recordings", "source")
