"""the history behind the necklace: ir_coverage_events

ENG-445. ``ir_sessions.coverage_state`` is a JSON tracker overwritten in place. It says
where a session's beads ended up and nothing else: not which session moved one, not what
the necklace looked like while an earlier session was still running. The Desk needs both —
the element list names the session that touched each element, and every session card shows
the portrait at the end of that session.

**The state stays.** This table is the history beside it, not a replacement for it. Reads
of the current state keep going to ``coverage_state``; making every read fold the history
would trade a JSON column for a table scan and gain nothing a session card cannot already
get.

**One row per transition, not per turn.** The classifier runs after every turn and mostly
reports beads that are already where it says. The service compares before writing, so a
session of forty turns that moved six beads leaves six rows. The unique constraint is the
same rule as a shape the database can hold: coverage only moves forward, so a session
reaches a given status on a given bead exactly once.

**``project_id`` and ``pericope`` are copied from the session.** Element keys come from the
canon — ``being:B3`` is Naomi in every project that works this passage, and repeats across
the passages she appears in — so a key alone does not name a bead. Both columns sit in the
index that answers "which session touched this one last" in one lookup, and both are null
or trivial to no one: the project is null exactly where the session's is, which today is
everywhere, until the room app sends its device credential in ENG-454.

**What the backfill can derive, and what it cannot.**

Derivable, and derived: the bead each existing session ended on. Every element in a stored
``coverage_state`` above ``not_encountered`` becomes one event, carrying that session's
project and passage.

Not derivable, and therefore absent rather than invented:

- *When a bead moved.* Nothing recorded it. The backfilled rows are stamped with the
  session's ``updated_at``, which is the last thing that happened to that session and not
  the moment of the transition. Within one backfilled session every event shares that
  instant, so the order its beads moved in is not recoverable and is not implied.
- *The step through ``surfaced``.* A bead that ended ``engaged`` gets one event. It may
  have been classified ``surfaced`` first, or gone straight to ``engaged`` in a single
  turn; the state cannot tell the two apart, and writing both would put a transition in
  the history that nobody can point at.
- *Which session moved a bead first, among sessions that share an ``updated_at``.* Ordering
  by a timestamp that stands for "when this session was last written" answers "who touched
  it last" only as well as that stands in for it. For sessions opened from here on, the
  events carry their own instants and the answer is exact.
- *Nothing at all for a panorama session.* It has no coverage spine and its
  ``coverage_state`` is empty, so it contributes no events, which is the true answer and
  not a gap.

Going back down drops the table and the derived rows with it. The derivable half is
rebuilt on the way up; the transitions recorded live in between are not, because
``coverage_state`` never held them.

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20 00:00:00.000000
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0002"
down_revision: str | None = "20260820_0001"
branch_labels = None
depends_on = None


TABLE = "ir_coverage_events"
INDEX = "ix_ir_coverage_events_element_touched"
UNTOUCHED = "not_encountered"


def _coverage_of(stored: Any) -> dict[str, str]:
    """``coverage_state`` comes back as a dict on PostgreSQL and as text on SQLite."""
    if isinstance(stored, str):
        return json.loads(stored or "{}")
    return stored or {}


def _backfill() -> None:
    bind = op.get_bind()
    sessions = bind.execute(
        sa.text("SELECT id, project_id, pericope, coverage_state, updated_at FROM ir_sessions")
    ).all()

    derived = [
        {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "project_id": project_id,
            "pericope": pericope,
            "element_key": element_key,
            "status": status,
            "at": updated_at,
        }
        for session_id, project_id, pericope, coverage_state, updated_at in sessions
        for element_key, status in _coverage_of(coverage_state).items()
        if status != UNTOUCHED
    ]
    if not derived:
        return

    bind.execute(
        sa.text(
            f"INSERT INTO {TABLE} (id, session_id, project_id, pericope, element_key,"
            " status, at) VALUES (:id, :session_id, :project_id, :pericope, :element_key,"
            " :status, :at)"
        ),
        derived,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("pericope", sa.String(120), nullable=False),
        sa.Column("element_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "session_id", "element_key", "status", name="uq_ir_coverage_events_step"
        ),
    )
    op.create_index(INDEX, TABLE, ["project_id", "pericope", "element_key", "at"])
    _backfill()


def downgrade() -> None:
    op.drop_index(INDEX, table_name=TABLE)
    op.drop_table(TABLE)
