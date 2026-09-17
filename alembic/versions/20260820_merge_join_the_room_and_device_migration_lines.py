"""join the room and device migration lines

Two lines of work each wrote their first migration on top of ``20260812_0001``: the
internalization-room tables on one side, the device table and its credential on the
other. Neither knew about the other, so the graph forked and Alembic ends up with two
heads. ``alembic upgrade head`` refuses to choose between them, and that is the command
the deploy runs.

This revision does nothing. It exists only to name both tips as its parents, which
collapses them back to a single head — the mechanism Alembic offers for exactly this
shape.

**It is temporary, and this is the sentence to read before deleting it.** When the room
line reaches ``main``, the device line rebases on top of it and its first migration comes
to depend on the last room migration directly. At that point the graph is linear on its
own, this revision has nothing left to join, and it should be removed along with the
junction branch it was written for. Nothing else depends on it; removing it is deleting
this file.

Revision ID: 20260820_merge
Revises: 20260812_room07, 20260819_0001
Create Date: 2026-08-20 00:00:00.000000
"""

from __future__ import annotations

revision: str = "20260820_merge"
down_revision: tuple[str, str] = ("20260812_room07", "20260819_0001")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: this revision joins two lineages, it does not change a schema."""


def downgrade() -> None:
    """Nothing to undo. Going back through here restores the two heads."""
