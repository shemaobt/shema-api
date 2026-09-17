"""the recorded events follow the spine: one bead per entity in each scene, one per silence

The coverage spine changed shape twice in one pass. An entity is a bead in every scene it
appears in now, keyed ``being:S4:B3`` where it used to be ``being:B3`` once for the whole
passage; a preservation rule about the same silence as a scene's absence rides on that
absence bead instead of standing as ``preserved:R6`` beside it; and the four Level-1 axes
open every necklace. ``necklace_with_touches`` reads strictly by ``element_key``, so an
event left under an old key would answer nothing: the team's work on Naomi, the famine
and the missing act of God would read as never touched the day this shipped.

**An entity's events move to the scene its old bead stood in.** The old bead carried the
scene the entity first appeared in — that is what ``Element.scene`` said and what the
necklace drew — so ``being:B3`` in P01 becomes ``being:S1:B3``, and scenes 2 to 4 stay
``not_encountered``. Spreading one old event over four scenes would keep the defect this
pass removes: "Naomi" said in scene 1 must not answer for "the woman" in scene 4.

**A folded rule's events land on the absences it folds into.** ``preserved:R6`` in P01 is
the missing act of God, which is the silence of scenes 1, 2 and 4; one recorded event
becomes one row on each of those absence beads, with the same status and instant. The
matcher is the spine's own, so what folds here is exactly what folds in ``elements_of``.

**The axes need no rows.** A bead with no event reads ``not_encountered``, which is the
honest answer for every session recorded before the axes existed.

Anything unmapped is left alone: a key the canon never held, and every key the new spine
still serves, stay as they are. Going back down puts the entity keys back; the folded
rows stay on the absence beads, where the old spine reads them as the same silence noticed
in that scene, and ``preserved:R6`` reads as not encountered again — under-counting, which
is the safe side of the floor.

Revision ID: 20260916_spine01
Revises: 20260916_ver01
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from app.services.internalization_room.canon.parse_map import MeaningMap

revision = "20260916_spine01"
down_revision = "20260916_ver01"
branch_labels = None
depends_on = None

TABLE = "ir_coverage_events"
ENTITY_KINDS = {"being", "place", "object", "time"}


def _entity_keys(meaning_map: MeaningMap) -> list[tuple[str, str]]:
    """Every per-scene entity key beside the passage-wide key the old spine wrote, in bead order.

    The canon is imported here and not at the top: `scripts/downgrade_targets.py` loads every
    revision without the app's settings, and `app.services` cannot be imported without them.
    """
    from app.services.internalization_room.canon.elements import elements_of
    from app.services.internalization_room.canon.parse_map import ROOM_BOOK

    pairs: list[tuple[str, str]] = []
    for element in elements_of(meaning_map, book=ROOM_BOOK):
        if element.kind.value in ENTITY_KINDS:
            kind, _scene, tail = element.key.split(":", 2)
            pairs.append((f"{kind}:{tail}", element.key))
    return pairs


def _entity_moves(meaning_map: MeaningMap) -> dict[str, str]:
    """Old entity key → the per-scene key of the scene the old bead stood in (its first)."""
    moves: dict[str, str] = {}
    for old, new in _entity_keys(meaning_map):
        moves.setdefault(old, new)
    return moves


def _rule_folds(meaning_map: MeaningMap) -> dict[str, list[str]]:
    """Old preservation-rule key → the absence keys of the scenes it folds into."""
    from app.services.internalization_room.canon.book_material import preservation_rules
    from app.services.internalization_room.canon.parse_map import ROOM_BOOK

    folds: dict[str, list[str]] = {}
    for rule in preservation_rules(ROOM_BOOK):
        if rule.pericope != meaning_map.pericope_num:
            continue
        into = [
            f"absence:{scene.number}"
            for scene in meaning_map.scenes
            if scene.absence and rule.folds_into(scene.absence)
        ]
        if into:
            folds[f"preserved:{rule.rule_id}"] = into
    return folds


def _maps() -> tuple[MeaningMap, ...]:
    from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book

    return load_book(ROOM_BOOK)


def _rekey(pericope: str, old: str, new: str) -> None:
    op.get_bind().execute(
        sa.text(
            f"UPDATE {TABLE} SET element_key = :new WHERE pericope = :pericope AND element_key = :old"
        ),
        {"new": new, "old": old, "pericope": pericope},
    )


def upgrade() -> None:
    bind = op.get_bind()
    for meaning_map in _maps():
        pericope = meaning_map.pericope_num
        for old, new in _entity_moves(meaning_map).items():
            _rekey(pericope, old, new)
        for old, absences in _rule_folds(meaning_map).items():
            first, *others = absences
            if others:
                rows = bind.execute(
                    sa.text(
                        f"SELECT session_id, project_id, status, at FROM {TABLE}"
                        " WHERE pericope = :pericope AND element_key = :old"
                    ),
                    {"pericope": pericope, "old": old},
                ).all()
                copies = [
                    {
                        "id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "project_id": project_id,
                        "pericope": pericope,
                        "element_key": absence,
                        "status": status,
                        "at": at,
                    }
                    for session_id, project_id, status, at in rows
                    for absence in others
                ]
                if copies:
                    bind.execute(
                        sa.text(
                            f"INSERT INTO {TABLE} (id, session_id, project_id, pericope,"
                            " element_key, status, at) VALUES (:id, :session_id, :project_id,"
                            " :pericope, :element_key, :status, :at)"
                        ),
                        copies,
                    )
            _rekey(pericope, old, first)


def downgrade() -> None:
    for meaning_map in _maps():
        for old, new in _entity_keys(meaning_map):
            _rekey(meaning_map.pericope_num, new, old)
