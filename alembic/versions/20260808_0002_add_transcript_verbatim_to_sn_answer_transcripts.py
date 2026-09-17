"""add transcript_verbatim to sn_answer_transcripts

The disfluency cleanup (ENG-395) replaced the only record of what was said: the verbatim
speech-to-text output lived in a local variable and was discarded once the cleaned text was
written. This column keeps it, so a sentence the cleaner removed can still be inspected
against the one the facilitator confirmed.

Nullable with no default and no backfill. A row written before this revision has no
verbatim text and never will — there is nothing left to recover it from — and NULL says
exactly that, where copying `transcript_source` into it would claim the two were compared
when nothing ever compared them.

Adds one column to one sn_* table. This database is shared with every other Tripod app, so
nothing here alters or drops anything it did not create.

Revision ID: 20260808_0002
Revises: 20260808_0001
Create Date: 2026-08-08 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0002"
down_revision: str | None = "20260808_0001"
branch_labels = None
depends_on = None


TABLE_NAME = "sn_answer_transcripts"
COLUMN_NAME = "transcript_verbatim"


def upgrade() -> None:
    op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE_NAME, COLUMN_NAME)
