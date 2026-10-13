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
becomes one row on each of those absence beads, with the same status and instant. What
folds is what the spine folded on 16 September, written out below.

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

import re
import uuid

import sqlalchemy as sa

from alembic import op

revision = "20260916_spine01"
down_revision = "20260916_ver01"
branch_labels = None
depends_on = None

TABLE = "ir_coverage_events"
SCENE_KEY = re.compile(r"^(being|place|object|time):S\d+:(.+)$")
ENTITY_KEYS = {
    "P01": """
        being:S1:B2 being:S1:B3 being:S1:B4 being:S1:B5 being:S1:B1 being:S1:B6 place:S1:PL1
        place:S1:PL2 place:S1:PL_LAND_OF_JUDAH object:S1:O1 object:S1:CB_0030
        time:S1:TM_PERIOD_OF_JUDGES being:S2:B2 being:S2:B3 being:S2:B4 being:S2:B5 place:S2:PL2
        being:S3:B4 being:S3:B5 being:S3:B7 being:S3:B8 being:S3:B9 being:S3:B3 place:S3:PL2
        object:S3:TH_TEN_YEARS_APPROXIMATELY being:S4:B4 being:S4:B5 being:S4:B3 place:S4:PL2
    """.split(),
    "P02": """
        being:S1:B3 being:S1:B8 being:S1:B9 being:S1:B10 being:S1:B31 place:S1:PL2
        place:S1:PL_LAND_OF_JUDAH place:S1:the-road object:S1:CB_0012 being:S2:B3 being:S2:B8
        being:S2:B9 being:S2:B10 being:S2:B2 being:S2:B31 place:S2:PL_EACH_HER_MOTHERS_HOUSE
        place:S2:the-road object:S2:CB_0011 object:S2:CB_0008 object:S2:CB_0014 being:S3:B3
        being:S3:B8 being:S3:B9 being:S3:B10 place:S3:the-road
    """.split(),
    "P03": """
        being:S1:B3 being:S1:B9 being:S1:B8 place:S1:the-road place:S1:PL2 being:S2:B9 being:S2:B3
        being:S2:B10 being:S2:B31 place:S2:the-road place:S2:where-wherever being:S3:B3 being:S3:B9
        place:S3:the-road
    """.split(),
    "P04": """
        being:S1:B3 being:S1:B9 being:S1:B28 being:S1:B24 place:S1:PL1 place:S1:PL2 being:S2:B3
        being:S2:B24 being:S2:B10 being:S2:B12 place:S2:PL1
        place:S2:out-back-the-going-and-coming-in being:S3:B3 being:S3:B9 place:S3:PL1 place:S3:PL2
        object:S3:CB_0026 time:S3:at-the-beginning-of-the-barley-h
    """.split(),
    "P05": """
        being:S1:B13 being:S1:B3 being:S1:B2 being:S1:B29 object:S1:CB_0032 being:S2:B9 being:S2:B3
        place:S2:PL_NAOMIS_DWELLING place:S2:the-field-the-place-she-means-to object:S2:CB_0033
        object:S2:CB_0034 being:S3:B9 being:S3:B13 being:S3:B14 being:S3:B10 being:S3:B29
        place:S3:PL5 place:S3:PL5_BOAZ_PORTION place:S3:PL1 object:S3:CB_0035 object:S3:CB_0008
        being:S4:B13 being:S4:B15 being:S4:B9 being:S4:B3 being:S4:B14 place:S4:PL5_BOAZ_PORTION
        place:S4:PL2 place:S4:PL_HA_BAYIT_FIELD_SHELTER object:S4:from-morning-until-now-how-long-
    """.split(),
    "P06": """
        being:S1:B13 being:S1:B9 being:S1:B16 being:S1:B17 place:S1:PL5_BOAZ_PORTION
        place:S1:PL_OTHER_FIELD place:S1:the-vessels object:S1:CB_0034 being:S2:B9 being:S2:B13
        being:S2:B3 being:S2:ruth-s-deceased-husband-your-hus
        being:S2:ruth-s-father-and-mother-your-fa being:S2:B10 place:S2:PL5_BOAZ_PORTION
        place:S2:the-land-of-your-birth place:S2:a-people-you-did-not-know object:S2:CB_0033
        object:S2:CB_0038 object:S2:CB_0037 object:S2:CB_0008 being:S3:B13 being:S3:B9 being:S3:B14
        place:S3:PL5_BOAZ_PORTION object:S3:CB_0012 object:S3:O9 object:S3:O10 time:S3:TM_MEALTIME
        being:S4:B13 being:S4:B17 being:S4:B9 place:S4:PL5_BOAZ_PORTION place:S4:among-the-sheaves
        object:S4:CB_0034 object:S4:O11
    """.split(),
    "P07": """
        being:S1:B9 place:S1:PL5_BOAZ_PORTION object:S1:CB_0034 object:S1:CB_0041 object:S1:O12
        object:S1:O2 time:S1:TM_EVENING being:S2:B9 being:S2:B3 place:S2:PL4
        place:S2:PL_NAOMIS_DWELLING object:S2:O12 object:S2:O10 being:S3:B3 being:S3:B9 being:S3:B13
        being:S3:B10 being:S3:B18 being:S3:the-dead-of-the-household-the-de being:S3:B17
        being:S3:B16 place:S3:PL_NAOMIS_DWELLING place:S3:PL5_BOAZ_PORTION place:S3:PL_OTHER_FIELD
        object:S3:CB_0008 object:S3:CB_0011 object:S3:CB_0039 object:S3:CB_0001 time:S3:TM_TODAY
        being:S4:B9 being:S4:B16 being:S4:B13 being:S4:B3 place:S4:PL5_BOAZ_PORTION
        place:S4:PL_NAOMIS_DWELLING object:S4:CB_0018 object:S4:CB_0026
        time:S4:TM_EXTENDED_HARVEST_SPAN
    """.split(),
    "P08": """
        being:S1:B3 being:S1:B9 being:S1:B13 being:S1:B16 place:S1:PL_NAOMIS_DWELLING place:S1:PL6
        object:S1:CB_0014 object:S1:O2 object:S1:O13 object:S1:CB_0042 being:S2:B9 being:S2:B3
        place:S2:PL_NAOMIS_DWELLING
    """.split(),
    "P09": """
        being:S1:B9 being:S1:B13 being:S1:B3 place:S1:PL6 place:S1:PL_END_OF_GRAIN_HEAP
        object:S1:CB_0042 being:S2:B13 being:S2:B9 being:S2:B18 place:S2:PL6 object:S2:CB_0037
        object:S2:CB_0001 time:S2:TM_MIDDLE_OF_THE_NIGHT being:S3:B13 being:S3:B9 being:S3:B10
        being:S3:B19 being:S3:B21 being:S3:the-young-men place:S3:PL6 place:S3:PL7 object:S3:CB_0008
        object:S3:CB_0011 object:S3:CB_0032 object:S3:CB_0006 object:S3:CB_0001
        time:S3:TM_NIGHT_UNTIL_MORNING
    """.split(),
    "P10": """
        being:S1:B9 being:S1:B13 place:S1:PL6 place:S1:PL4 object:S1:CB_0042 object:S1:O13
        object:S1:O16 time:S1:TM_NIGHT_TO_MORNING being:S2:B3 being:S2:B9 being:S2:B13
        place:S2:PL_NAOMIS_DWELLING object:S2:O16 object:S2:CB_0044 object:S2:CB_0024
        object:S2:CB_0043 object:S2:O19 time:S2:TM_TODAY
    """.split(),
    "P11": """
        being:S1:B13 being:S1:B19 being:S1:B20 place:S1:PL7 object:S1:CB_0006 object:S1:CB_0001
        object:S1:CB_0045 being:S2:B13 being:S2:B19 being:S2:B20 being:S2:B3 being:S2:B2
        place:S2:PL7 place:S2:PL5_ELIMELECH_PORTION place:S2:PL2 object:S2:CB_0003 being:S3:B13
        being:S3:B19 being:S3:B9 being:S3:B3 being:S3:the-dead-the-dead place:S3:PL7
        object:S3:CB_0005 object:S3:CB_0002 object:S3:CB_0039 object:S3:CB_0003 object:S3:CB_0004
        time:S3:TM_DAY_OF_PURCHASE being:S4:B19 being:S4:B13 place:S4:PL7 place:S4:PL_ISRAEL
        object:S4:O26 object:S4:CB_0007 time:S4:TM_FORMER_TIMES
    """.split(),
    "P12": """
        being:S1:B13 being:S1:B20 being:S1:B21 being:S1:B2 being:S1:B5 being:S1:B4 being:S1:B3
        being:S1:B9 being:S1:the-dead-the-dead place:S1:PL7 object:S1:CB_0001 object:S1:CB_0005
        object:S1:CB_0002 object:S1:CB_0039 object:S1:CB_0003 object:S1:CB_0004 object:S1:CB_0006
        time:S1:TM_TODAY being:S2:B21 being:S2:B20 being:S2:B10 being:S2:B13 being:S2:B9
        being:S2:B22 being:S2:B27 being:S2:B23 being:S2:B30 place:S2:PL7 place:S2:PL_ISRAEL
        place:S2:PL8 place:S2:PL1 object:S2:CB_0008 object:S2:CB_0010 object:S2:CB_0009
        object:S2:CB_0049
    """.split(),
    "P13": """
        being:S1:B13 being:S1:B9 being:S1:B10 being:S1:the-child-a-son place:S1:PL_NAOMIS_DWELLING
        object:S1:CB_0001 being:S2:B24 being:S2:B3 being:S2:B10 being:S2:the-child-a-redeemer
        being:S2:B9 place:S2:PL_ISRAEL object:S2:CB_0008 object:S2:CB_0001 object:S2:CB_0005
        object:S2:CB_0046 being:S3:B3 being:S3:the-child-the-child being:S3:B24 being:S3:B25
        being:S3:B26 place:S3:PL_NAOMIS_DWELLING object:S3:CB_0047 object:S3:CB_0048
    """.split(),
    "P14": """
        being:S1:B27 being:S1:B13 being:S1:B25 being:S1:B26 object:S1:CB_0049 object:S1:CB_0005
        object:S1:CB_0047 object:S1:CB_0048
    """.split(),
}
RULE_FOLDS = {
    "P01": {
        "preserved:R6": ["absence:1", "absence:2", "absence:4"],
        "preserved:R7": ["absence:2", "absence:4"],
    },
    "P07": {"preserved:R13": ["absence:3"]},
}


def _entity_keys(pericope: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key in ENTITY_KEYS[pericope]:
        kind, _scene, tail = key.split(":", 2)
        pairs.append((f"{kind}:{tail}", key))
    return pairs


def _entity_moves(pericope: str) -> dict[str, str]:
    """Old entity key → the per-scene key of the scene the old bead stood in (its first)."""
    moves: dict[str, str] = {}
    for old, new in _entity_keys(pericope):
        moves.setdefault(old, new)
    return moves


def _rekey(pericope: str, old: str, new: str) -> None:
    op.get_bind().execute(
        sa.text(
            f"UPDATE {TABLE} SET element_key = :new WHERE pericope = :pericope AND element_key = :old"
        ),
        {"new": new, "old": old, "pericope": pericope},
    )


def upgrade() -> None:
    bind = op.get_bind()
    for pericope in ENTITY_KEYS:
        for old, new in _entity_moves(pericope).items():
            _rekey(pericope, old, new)
        for old, absences in RULE_FOLDS.get(pericope, {}).items():
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
    stored = op.get_bind().execute(sa.text(f"SELECT DISTINCT pericope, element_key FROM {TABLE}"))
    for pericope, key in stored.all():
        scene_key = SCENE_KEY.match(key)
        if scene_key:
            _rekey(pericope, key, f"{scene_key[1]}:{scene_key[2]}")
