"""ENG-450 follow-up — a coverage state with no rank must break loudly, not quietly.

`case(_RANK_OF, value=..., else_=0)` is how the rank scale is taught to SQL, and `else_=0`
maps anything unranked to `not_encountered`. That is not a defect to fix in SQL: there is no
way to raise from inside a `CASE`, and `else_=NULL` lands in the same place, because `MAX`
ignores nulls and the caller reads a missing bead as `not_encountered` anyway.

So the defence belongs where the map is **built**. A state that reaches the enum without
reaching `_RANK` would come back from the database as never touched — every partially engaged
bead, silently — and the passage would un-close itself with nothing red anywhere.

**Which enum the guard compares against is the whole decision, and it was measured.** The
obvious form — `set(_RANK) == set(CoverageStatus)`, with whatever `CoverageStatus` is in
scope — **does not bite** the case it exists for. Reproduced: a merge resolution that leaves a
local three-state class shadowing the shared four-state one shadows the map with it, so both
sides have three, set equality holds, and `partially_engaged` quietly ranks 0. Measured on
2026-08-21:

    forma A (escopo local)      chaves 3, membros 3   MORDE? False
    forma B (enum canônico)     faltando: partially_engaged   MORDE? True

The guard therefore names `app.core.room_enums` explicitly, and these cases are what stop it
being "simplified" back into the version that cannot fail.
"""

from __future__ import annotations

import enum

from app.core.room_enums import CoverageStatus
from app.services.internalization_room.coverage import _RANK, unranked


def test_every_coverage_state_has_a_rank_today() -> None:
    assert unranked(_RANK, CoverageStatus) == set()


def test_a_state_that_reaches_the_enum_without_a_rank_is_named() -> None:
    """The case the guard exists for: the enum grew and the map did not."""
    a_map_left_behind = {
        CoverageStatus.NOT_ENCOUNTERED: 0,
        CoverageStatus.SURFACED: 1,
        CoverageStatus.ENGAGED: 3,
    }

    assert unranked(a_map_left_behind, CoverageStatus) == {"partially_engaged"}


def test_the_guard_is_useless_against_a_scale_that_shadows_the_enum_with_it() -> None:
    """Why the canonical enum is the argument, asserted rather than left to a comment.

    A three-state class shadowing the four-state one takes the map down with it, and a guard
    reading the shadowed name compares three against three and sees nothing wrong. This is the
    version of the check that would have shipped as a second piece of green-over-empty — so it
    is written down as a case, failing to bite, beside the one that bites.
    """

    class ShadowedStatus(enum.StrEnum):
        NOT_ENCOUNTERED = "not_encountered"
        SURFACED = "surfaced"
        ENGAGED = "engaged"

    shadowed_map = {member: rank for rank, member in enumerate(ShadowedStatus)}

    assert unranked(shadowed_map, ShadowedStatus) == set(), (
        "o cenário do sombreamento mudou; reveja qual enum o portão compara"
    )
    assert unranked(shadowed_map, CoverageStatus) == {"partially_engaged"}


def test_the_module_refuses_to_import_with_a_holed_scale(tmp_path) -> None:
    """The property `boots` turns into a red import in twenty-three seconds.

    Exercised on a copy, because the point is what happens at **import time** and the real
    module is already imported by the time any test runs.
    """
    import importlib.util
    from pathlib import Path

    source = Path("app/services/internalization_room/coverage.py").read_text(encoding="utf-8")
    holed = source.replace("    CoverageStatus.PARTIALLY_ENGAGED: 2,\n", "")
    assert holed != source, "o mapa mudou de forma; este caso não está mais furando nada"

    copy = tmp_path / "coverage_holed.py"
    copy.write_text(holed, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("coverage_holed", copy)
    assert spec and spec.loader

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except RuntimeError as refused:
        assert "partially_engaged" in str(refused)
    else:
        raise AssertionError("um estado sem rank importou em silêncio")
