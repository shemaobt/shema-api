"""stored coverage follows her ids: the axes, the scenes and the silences are spelled as hers

The spine writes her ids now: ``L1:arc`` for ``arc``, ``scene:S1`` for ``scene:1`` and
``absence:S1`` for ``absence:1``. Every reader looks a bead up by its id, so a session stored
before this would open with its axes, scenes and silences untouched. The rename is a spelling
and reads no canon: ``coverage_state`` keys, coverage events and question anchors move to the
new spelling, a status is never lowered where the new id is already stored, and walking down
spells them back. An id that is neither shape is left as it is.

Revision ID: 20261012_spine02
Revises: 20261011_cons01
"""

import re
from collections.abc import Callable

import sqlalchemy as sa

from alembic import op

revision = "20261012_spine02"
down_revision = "20261011_cons01"
branch_labels = None
depends_on = None

AXIS = "arc|context|tone|function"
RANK = {"not_encountered": 0, "partially_engaged": 1, "surfaced": 2, "engaged": 3}

SESSIONS = sa.table("ir_sessions", sa.column("id", sa.String), sa.column("coverage_state", sa.JSON))


def _hers(key: str) -> str:
    key = re.sub(rf"^({AXIS})$", r"L1:\1", key)
    return re.sub(r"^(scene|absence):(\d+)$", r"\1:S\2", key)


def _ours(key: str) -> str:
    key = re.sub(rf"^L1:({AXIS})$", r"\1", key)
    return re.sub(r"^(scene|absence):S(\d+)$", r"\1:\2", key)


def _respell_coverage(spell: Callable[[str], str]) -> None:
    bind = op.get_bind()
    for session_id, coverage in bind.execute(sa.select(SESSIONS.c.id, SESSIONS.c.coverage_state)):
        if not coverage:
            continue
        respelled: dict[str, str] = {}
        for key, status in coverage.items():
            new = spell(key)
            standing = respelled.get(new)
            if standing is None or RANK[status] > RANK[standing]:
                respelled[new] = status
        if respelled != coverage:
            bind.execute(
                sa.update(SESSIONS)
                .where(SESSIONS.c.id == session_id)
                .values(coverage_state=respelled)
            )


def _respell_column(table: str, spell: Callable[[str], str]) -> None:
    bind = op.get_bind()
    keys = bind.execute(
        sa.text(f"SELECT DISTINCT element_key FROM {table} WHERE element_key IS NOT NULL")
    ).scalars()
    for old in list(keys):
        new = spell(old)
        if new != old:
            bind.execute(
                sa.text(f"UPDATE {table} SET element_key = :new WHERE element_key = :old"),
                {"new": new, "old": old},
            )


def _respell(spell: Callable[[str], str]) -> None:
    _respell_coverage(spell)
    _respell_column("ir_coverage_events", spell)
    _respell_column("ir_questions", spell)


def upgrade() -> None:
    _respell(_hers)


def downgrade() -> None:
    _respell(_ours)
