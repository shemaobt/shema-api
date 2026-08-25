"""when a conversation ended: ir_sessions.ended_at

ENG-451. A session had a start and no end. The Desk's third column is one card per
conversation with its date, its length and its state, and none of the three could be
answered: `created_at` alone says when the team sat down and nothing about when they got up.

**Only an end that happened is stamped here.** A session closes in one of two ways. The
completion floor closing it is an event, at an instant, and that instant is written into
this column. A session nobody closed is the other way, and nothing is written: its end is
derived at read time from its last activity.

That asymmetry is the point rather than a convenience. The limit that decides how long a
quiet session may sit before it is over is shared with the room app's resume work (ENG-435)
and **is not agreed yet**. Derived, the day the two sides settle on a different number it
changes in one place and every past session re-answers correctly. Written into rows, it
freezes a number nobody agreed and needs a backfill to undo. It also makes the length
impossible to inflate: a session left at 15:00 and first asked about at 03:00 reports up to
15:00, because the end is the team's last activity and never the moment somebody looked.

**The backfill, and what it can derive.** Derivable, and derived: a session already `done`
closed at its last write, because nothing writes to a session after the settle that closes
it. Without it every conversation ever finished would come back to the Desk as abandoned —
the read derives an abandonment from staleness and a completion from a stamp, so a finished
row with no stamp is a completion nobody can see.

Not derivable, and therefore left null: a session still `in_progress` or halted at
`needs_person`. Both are open, both end by the idle rule, and neither has an end to record.

Nothing is indexed. This column is read on rows already selected by project and never
filtered or ordered on.

Revision ID: 20260820_0003
Revises: 20260820_0002
Create Date: 2026-08-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0003"
down_revision: str | None = "20260820_0002"
branch_labels = None
depends_on = None

TABLE = "ir_sessions"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text(
            f"UPDATE {TABLE} SET ended_at = updated_at"  # noqa: S608 - no interpolated input
            " WHERE status = 'done' AND ended_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column(TABLE, "ended_at")
