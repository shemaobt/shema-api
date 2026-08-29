"""ENG-589 — a passage whose preservation layer nobody wrote is refused, not walked.

The completion floor the design names is *every concrete element of the map — each scene,
being, place, object, time, significant absence, **and preserved element** — engaged*. The
last eight passages of Ruth carry no `do_not_decide` audit entry at all, so their coverage
spine is built without a single `preserved:` bead and their comprehension pack without a
single `preserved_element` checkpoint. Nothing refused them: the room walked them, met a
floor that was missing its top row, and handed Refine a package claiming the floor was met.

Two tests carry the slice, in opposite directions.

**`test_a_passage_with_no_preservation_layer_does_not_open`** is the gate. It fails against
the original code by the session being created normally.

**`test_a_passage_that_carries_its_preservation_layer_still_opens`** is the counterweight,
and is the more important of the two. A guard that overshoots takes the whole book down —
six passages that are walkable today, and the room with them.

The canon is read here rather than named: a test that wrote "P07 to P14" would keep passing
on the day the project writes those eight layers, which is exactly the day it must stop.
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.room_enums import ElementKind
from app.services.internalization_room.canon import book_material, parse_map
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.sessions import create_session

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]

WITH_LAYER = next(
    pericope
    for pericope in CANON
    if any(element.kind is ElementKind.PRESERVED for element in elements_for(pericope))
)
WITHOUT_LAYER = next(
    pericope
    for pericope in CANON
    if not any(element.kind is ElementKind.PRESERVED for element in elements_for(pericope))
)

#: A whole little canon of its own — one map and one Compilation Log — so the two signals can
#: be set against each other. The real Ruth material has them agreeing everywhere, and
#: agreement is not the same as either one being read.
_PENDING_MAP = textwrap.dedent(
    """\
    ---
    type: "pericope"
    pericope-num: "Q01"
    pericope-title: "A fixture, not canon"
    bcv: "Fable 1:1-2"
    genre-group: "NARRATIVE"
    genre: "HISTORICAL_NARRATIVE"
    status: "complete"
    sta-status: "pending"
    ---

    # Q01 — Fable 1:1-2

    ## 2. Level 1 — Whole-Passage Movement
    ### 2.1 Prose Arc
    Someone stands somewhere, and the telling stops there.

    ### 2.2 Context
    None. This passage exists only inside this test.

    ## 3. Level 2 — Scenes / Episodes

    ### Scene 1 — The only scene (v.1-2)

    **3A — Beings**
    [[B1-Someone]] — מִישֶׁהוּ / Someone

    **3B — Places**
    [[PL1-Somewhere]] — אֵיפֹשֶׁהוּ / Somewhere

    **3E — What Happens**
    Someone stands somewhere.

    **Significant Absence**
    Nobody says why.
    """
)

_LOG_WITH_A_LAYER = textwrap.dedent(
    """\
    # Q01 — COMPILATION LOG

    {
      "high_risk_register_audit": [
        {
          "id": "R1",
          "kind": "SILENCE",
          "note": "The telling never says why. Kept as it stands.",
          "do_not_decide": true,
          "required_in_audit": true
        }
      ]
    }
    """
)


@pytest.fixture
def a_passage_whose_survey_is_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """A passage the project has not signed off, and whose preservation layer *is* written.

    Nothing of Ruth is touched. The point of writing the layer is that the survey being
    pending has to carry the refusal on its own.
    """
    maps = tmp_path / "meaning-map"
    logs = tmp_path / "compilation-log"
    maps.mkdir()
    logs.mkdir()
    (maps / "Q01-Fable-1-1-2.md").write_text(_PENDING_MAP, encoding="utf-8")
    (logs / "Q01-Fable-1-1-2-COMPILATION-LOG.md").write_text(_LOG_WITH_A_LAYER, encoding="utf-8")

    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    _forget_the_canon()
    yield "Q01"
    _forget_the_canon()


def _forget_the_canon() -> None:
    parse_map.load_map.cache_clear()
    parse_map.load_book.cache_clear()
    book_material.preservation_rules.cache_clear()


async def test_a_passage_with_no_preservation_layer_does_not_open(
    db_session: AsyncSession,
) -> None:
    """The gate. Refused, and the refusal says which layer is missing and for which passage."""
    with pytest.raises(ValidationError) as refusal:
        await create_session(db_session, pericope=WITHOUT_LAYER)

    said = str(refusal.value)
    assert WITHOUT_LAYER in said
    assert "preservation" in said.lower()


async def test_a_passage_that_carries_its_preservation_layer_still_opens(
    db_session: AsyncSession,
) -> None:
    """The counterweight: the six that are walkable today go on being walkable, spine intact."""
    preserved = [
        element.key for element in elements_for(WITH_LAYER) if element.kind is ElementKind.PRESERVED
    ]

    session = await create_session(db_session, pericope=WITH_LAYER)

    assert session.pericope == WITH_LAYER
    assert preserved
    assert set(preserved) <= set(session.coverage_state)


async def test_every_passage_the_canon_offers_either_carries_the_layer_or_is_refused(
    db_session: AsyncSession,
) -> None:
    """The rule, stated over the whole canon, so the next book cannot come in the same door."""
    opened = {}
    for pericope in CANON:
        try:
            await create_session(db_session, pericope=pericope)
        except ValidationError:
            opened[pericope] = False
        else:
            opened[pericope] = True

    carries_the_layer = {
        pericope: any(element.kind is ElementKind.PRESERVED for element in elements_for(pericope))
        for pericope in CANON
    }
    assert opened == carries_the_layer


async def test_a_map_whose_survey_is_pending_is_not_consumable_canon(
    db_session: AsyncSession, a_passage_whose_survey_is_pending: str
) -> None:
    """`sta-status` is the field that marks a map unfinished, and it has never been read."""
    with pytest.raises(ValidationError) as refusal:
        await create_session(db_session, pericope=a_passage_whose_survey_is_pending)

    assert a_passage_whose_survey_is_pending in str(refusal.value)
