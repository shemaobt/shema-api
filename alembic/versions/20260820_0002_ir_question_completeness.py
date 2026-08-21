"""carry element_key, duration_ms and transcript on ir_questions

ENG-447. A raised-hand card in the Desk shows which bead the question is about, how long the
recording runs and what was said. The row carried none of the three, so the card had a name,
a time and a play button and nothing else.

**All three are nullable, and each for its own reason.** ``element_key`` is missing on every
row written before this and on every app that has not shipped ENG-456 — a question that names
no element is the common case today, and the Desk renders that card. ``duration_ms`` and
``transcript`` come from work done outside this process (ffprobe, and the platform's STT), and
the question surviving that work's failure is a stated acceptance criterion: a card with audio
and no transcript is still answerable.

**Nothing is backfilled.** Both derivable columns could be filled by re-reading every stored
clip, and that is a job for a script somebody chooses to run, not for a migration that holds
a deploy while it downloads audio. Old cards read as cards from before the measurement — the
same shape as a question whose transcription failed, which the Desk already draws.

``transcript`` is ``Text`` rather than a bounded ``String``: a question is spoken for as long
as the person needs, and truncating what was said to fit a column would be a silent edit of
somebody's words.

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0002"
down_revision: str | None = "20260820_0001"
branch_labels = None
depends_on = None


TABLE = "ir_questions"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("element_key", sa.String(length=120), nullable=True))
    op.add_column(TABLE, sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column(TABLE, sa.Column("transcript", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE, "transcript")
    op.drop_column(TABLE, "duration_ms")
    op.drop_column(TABLE, "element_key")
