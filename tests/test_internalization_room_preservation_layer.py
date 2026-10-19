"""ENG-589 — a passage whose preservation layer nobody wrote is refused, not walked.

The completion floor the design names is *every concrete element of the map — each scene,
being, place, object, time, significant absence, **and preserved element** — engaged*. The
passage whose Compilation Log has no `do_not_decide` audit entry at all gets a coverage spine
built without a single `preserved:` bead and a comprehension pack without a single
`preserved_element` checkpoint. Nothing refused it: the room walked it, met a floor that was
missing its top row, and handed Refine a package claiming the floor was met.

Two tests carry the slice, in opposite directions.

**`test_a_finished_passage_with_no_recorded_rule_does_not_open_and_names_the_layer`** is the
gate. It fails against the original code by the session being created normally.

**`test_a_passage_that_carries_its_preservation_layer_still_opens`** is the counterweight,
and is the more important of the two. A guard that overshoots takes the whole book down —
every passage that carries its layer, and the room with them.

The canon is read here rather than named: a test that wrote a range of passages would keep
passing on the day the project writes a layer it had counted as missing, which is exactly the
day it must stop.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.room_enums import ElementKind
from app.services.internalization_room.canon import book_material
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.labels import LABELS_DIR
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.sessions import create_session

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]

#: The passages a team can actually be standing on — any the canon vendors that
#: `require_walkable` refuses are left out. Read from the canon, like `CANON` above, so this
#: grows with the book rather than needing an edit every time a passage opens.
WALKABLE = [
    meaning_map.pericope_num
    for meaning_map in load_book(ROOM_BOOK)
    if not book_material.unwalkable(meaning_map)
]


WITH_LAYER = next(
    pericope
    for pericope in CANON
    if any(element.kind is ElementKind.PRESERVED for element in elements_for(pericope))
)


async def test_a_passage_that_carries_its_preservation_layer_still_opens(
    db_session: AsyncSession,
) -> None:
    """The counterweight: a passage that carries its layer goes on being walkable, spine intact."""
    preserved = [
        element.key for element in elements_for(WITH_LAYER) if element.kind is ElementKind.PRESERVED
    ]

    session = await create_session(db_session, pericope=WITH_LAYER)

    assert session.pericope == WITH_LAYER
    assert preserved
    assert set(preserved) <= set(session.coverage_state)


def test_the_book_opens_from_ruth_1_1_to_ruth_4_22_with_no_hole_in_the_middle() -> None:
    maps = load_book(ROOM_BOOK)
    opens = [m.pericope_num for m in maps if not book_material.unwalkable(m)]
    ends_at = next(m.pericope_num for m in maps if m.reference == "Ruth 4:18-22")

    assert opens == CANON[: CANON.index(ends_at) + 1] == CANON, (
        f"o livro que se caminha vai de Rute 1:1 a 4:22, sem buraco no meio — abriram {opens}"
    )


@pytest.mark.parametrize("pericope_num", WALKABLE)
def test_every_preserved_bead_of_a_walkable_passage_has_a_label(pericope_num: str) -> None:
    """The inverse of `labels.py`'s orphans guard — ENG-925.

    `orphans` (`canon/labels.py`) catches a label the canon no longer serves; nothing caught
    the other direction until now. The re-vendor that almost shipped in ENG-787 added seven
    `preserved:*` beads to P07 with no matching catalogue entry.

    Reads the shipped `ruth.json` directly rather than going through `labelled_elements`:
    that loader builds its returned key set from the same `elements_for` call this test
    filters, so `preserved <= {e.key for e in labelled_elements(...)}` can never be false —
    it is either true, or the call raises first (`_text` refuses a missing key) and the
    comparison is never reached at all. Comparing against the catalogue's own keys instead
    also catches the shape that leaves `labelled_elements` silent: a walkable passage with
    *no* catalogue entry at all takes the canon fallback (`_from_the_canon` in `labels.py`) and
    answers every bead, preserved ones included, with `label_pt=None` and the canon's English
    in `label_en` — a real gap the exception-based version could not see, caught on the PR's
    bot review.
    """
    preserved = {
        element.key
        for element in elements_for(pericope_num)
        if element.kind is ElementKind.PRESERVED
    }
    catalogue = json.loads((LABELS_DIR / "ruth.json").read_text(encoding="utf-8"))
    named = set(catalogue.get(pericope_num, {}))

    assert preserved <= named
