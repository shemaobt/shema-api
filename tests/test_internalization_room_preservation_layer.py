from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.room_enums import ElementKind
from app.services.internalization_room.canon import book_material, parse_map
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.labels import LABELS_DIR
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.sessions import create_session
from tests.canon_harness import (
    A_FABLE_LOG_WITH_A_COMPLETE_REGISTER,
    a_fable_map,
    forget_the_canon,
)

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


@pytest.fixture
def a_passage_whose_survey_is_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """A passage the project has not signed off, and whose preservation layer *is* written.

    A whole little canon of its own — one map and one Compilation Log — so the two signals can
    be set against each other. The real Ruth material has them agreeing everywhere, and
    agreement is not the same as either one being read. Nothing of Ruth is touched. The point
    of writing the layer is that the survey being pending has to carry the refusal on its own.
    """
    maps = tmp_path / "meaning-map"
    logs = tmp_path / "compilation-log"
    maps.mkdir()
    logs.mkdir()
    (maps / "Q01-Fable-1-1-2.md").write_text(a_fable_map(sta_status="pending"), encoding="utf-8")
    (logs / "Q01-Fable-1-1-2-COMPILATION-LOG.md").write_text(
        A_FABLE_LOG_WITH_A_COMPLETE_REGISTER, encoding="utf-8"
    )

    monkeypatch.setattr(parse_map, "MAPS_DIR", maps)
    monkeypatch.setattr(book_material, "LOGS_DIR", logs)
    monkeypatch.setattr(book_material, "SERVED_BOOKS", frozenset({"Ruth", "Fable"}))
    forget_the_canon()
    yield "Q01"
    forget_the_canon()


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


async def test_a_map_whose_survey_is_pending_is_not_consumable_canon(
    db_session: AsyncSession, a_passage_whose_survey_is_pending: str
) -> None:
    """`sta-status` is the field that marks a map unfinished, and it has never been read."""
    with pytest.raises(ValidationError) as refusal:
        await create_session(db_session, pericope=a_passage_whose_survey_is_pending)

    assert a_passage_whose_survey_is_pending in str(refusal.value)


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
