from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

#: Re-exported so `_RANK` below reads beside the values it ranks. Defined in `core`
#: because `app/models` needs it too — see `app/core/room_enums.py`.
from app.core import room_enums
from app.core.room_enums import CoverageStatus
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import CoverageView
from app.services.internalization_room.canon.elements import (
    Element,
    ElementKind,
    absence_index,
    element_keys,
    elements_for,
)

PANORAMA_PREFIX = "OV-"


def is_panorama(pericope: str) -> bool:
    """`OV-Ruth` addresses the book itself rather than one of its passages.

    It lives here rather than beside the session service because what makes a panorama
    different, everywhere it matters, is that it has **no coverage spine**: there is no map
    to draw beads from, and every function in this module raises from the canon if it is
    handed one. Both the session service and the reconstruction below have to ask, and the
    reconstruction cannot import the session service without a cycle.
    """
    return pericope.startswith(PANORAMA_PREFIX)


_RANK = {
    CoverageStatus.NOT_ENCOUNTERED: 0,
    CoverageStatus.PARTIALLY_ENGAGED: 1,
    CoverageStatus.SURFACED: 2,
    CoverageStatus.ENGAGED: 3,
}


def unranked(rank: dict, canonical: type[StrEnum]) -> set[str]:
    """The states `canonical` holds that `rank` does not — by value, not by identity.

    By value because the two may be different class objects and still mean the same scale,
    which is exactly the case worth catching.
    """
    return {state.value for state in canonical} - {getattr(key, "value", key) for key in rank}


#: A state that reaches the enum without reaching `_RANK` is the one failure on this path that
#: cannot be seen. `case(_RANK_OF, value=..., else_=0)` teaches the scale to SQL, and an
#: unranked value lands on 0 — `not_encountered` — so every partially engaged bead would come
#: back from the database as never touched, the passage would un-close itself, and nothing
#: would be red. `ir_coverage_events.status` is a `String(32)` on purpose, so the schema does
#: not object either.
#:
#: The `else_` is not the place to fix it: SQL has no way to raise from inside a `CASE`, and
#: `else_=NULL` lands identically, because `MAX` ignores nulls and a missing bead already reads
#: as `not_encountered`. The defence belongs where the map is built, which is here.
#:
#: **Compared against `app.core.room_enums` by name, and that is the whole decision.** Checking
#: against whichever `CoverageStatus` is in local scope does not bite: a merge resolution that
#: leaves a three-state class shadowing the shared four-state one shadows this map with it, so
#: both sides carry three, set equality holds, and `partially_engaged` quietly ranks 0.
#: Measured — see `tests/test_coverage_rank_covers_the_scale.py`, which keeps the version that
#: cannot fail beside the one that can.
_UNRANKED = unranked(_RANK, room_enums.CoverageStatus)
if _UNRANKED:
    raise RuntimeError(
        "coverage states with no rank: "
        + ", ".join(sorted(_UNRANKED))
        + " — unranked states read back from the database as not_encountered"
    )


def ranks() -> dict[str, int]:
    """The scale as plain values, for a caller that has to teach it to something else.

    SQL cannot order a status name — `engaged` sorts before `surfaced` — so the query that
    rebuilds a past necklace has to be handed the order this module keeps.
    """
    return {status.value: rank for status, rank in _RANK.items()}


def initial_state(pericope_num: str) -> dict[str, str]:
    return dict.fromkeys(element_keys(pericope_num), CoverageStatus.NOT_ENCOUNTERED.value)


def merge(
    state: dict[str, str],
    *,
    pericope_num: str,
    surfaced: Iterable[str] = (),
    engaged: Iterable[str] = (),
) -> dict[str, str]:
    """Advance coverage. Movement is one-way: a status never drops back.

    An element named in more than one bucket lands on the furthest of them, whatever order
    the classifier listed it in — each step only moves forward.
    """
    merged = {**initial_state(pericope_num), **state}
    buckets = (
        (surfaced, CoverageStatus.SURFACED),
        (engaged, CoverageStatus.ENGAGED),
    )
    for keys, status in buckets:
        for key in keys:
            if key not in merged:
                continue
            if _RANK[status] > _RANK[CoverageStatus(merged[key])]:
                merged[key] = status.value
    return merged


def furthest(kept: dict[str, str], told: dict[str, str], *, pericope_num: str) -> dict[str, str]:
    """The better of two readings of the same spine, element by element.

    Two turns overlapping is ordinary: the classifier for turn seven takes a Gemini round
    trip, and turn eight can land and settle while it runs. Writing a whole snapshot over
    whatever is there now let the older reading win — and a bead the team had just earned
    went dark, so the room asked them to work an element they had already covered.

    Movement stays one-way, as it is within a single merge.
    """
    merged = {**initial_state(pericope_num), **kept}
    for key, status in told.items():
        if key not in merged:
            continue
        if _RANK[CoverageStatus(status)] > _RANK[CoverageStatus(merged[key])]:
            merged[key] = status
    return merged


def counts(state: dict[str, str]) -> dict[str, int]:
    """Two numbers, meaning what they have always meant.

    `engaged` is the beads the team worked in their own words; `surfaced` is the cumulative
    "encountered at least" figure — everything above `not_encountered`, which takes in a
    row still written under the retired status. The necklace fills a bead on `engaged`
    alone, so a passage the team only echoed shows every bead waiting.
    """
    engaged = sum(1 for value in state.values() if value == CoverageStatus.ENGAGED)
    surfaced = sum(1 for value in state.values() if value != CoverageStatus.NOT_ENCOUNTERED)
    return {"engaged": engaged, "surfaced": surfaced, "total": len(state)}


def coverage_view(session: IRSession) -> CoverageView:
    numbers = counts(session.coverage_state or {})
    return CoverageView(
        engaged=numbers["engaged"],
        surfaced=numbers["surfaced"],
        total=numbers["total"],
        absence_index=-1 if is_panorama(session.pericope) else absence_index(session.pericope),
    )


def remaining(state: dict[str, str], pericope_num: str) -> list[Element]:
    """What the team has not worked yet, with labels the Guide can act on.

    A bead short of `engaged` stays on this list whatever word it stands at, because this
    is the only way it can still be promoted — the classifier is shown this list and
    nothing else, so a bead dropped from it is frozen at whatever status it left with.
    """
    merged = {**initial_state(pericope_num), **state}
    return [
        element
        for element in elements_for(pericope_num)
        if merged.get(element.key) != CoverageStatus.ENGAGED
    ]


def current_scene(state: dict[str, str], pericope_num: str) -> str | None:
    """The first scene with a bead still short of `engaged`, once one scene bead is.

    Ledger state, read off which scene-scoped beads the team has worked: none of them
    engaged is the whole-passage opening, all of them engaged is the whole-passage
    integration, and both are answered with no scene at all. The pointer the rehearsal is
    read against lives in `live_turn` and answers to what the team has said, not to this.
    """
    merged = {**initial_state(pericope_num), **state}
    beads = [
        (element.scene, merged.get(element.key) == CoverageStatus.ENGAGED)
        for element in elements_for(pericope_num)
        if element.scene is not None
    ]
    if not any(engaged for _, engaged in beads):
        return None
    for scene in sorted({scene for scene, _ in beads}):
        if not all(engaged for at, engaged in beads if at == scene):
            return f"S{scene}"
    return None


_EXITS_AT_SURFACED = frozenset({"arc", "context", "tone", "function"})


def floor_met(state: dict[str, str], pericope_num: str) -> bool:
    """Every concrete element engaged; a Level-1 axis at least surfaced.

    Hard Rule #2 of her design: "**Only** `engaged` **counts for coverage.** `surfaced`
    (Guide mentioned it) is not enough. If `surfaced` ever counts as covered, sessions
    complete hollow" (`marcia/CLAUDE.md:31`). The floor once came down a step to meet the
    echo, on the argument that a preservation rule is mostly engaged as the team taking up
    the Guide's noticing and that demanding more of all five of Ruth 1's made a passage
    that never closes. Her classifier settles that at the other end: the echo of a silence
    is written `engaged`, so the floor asks the full reading of every bead and the silences
    are the beads a team can fill by taking them up. A bead still standing at the retired
    `partially_engaged` is one the ledger has not seen the team take up, and it holds the
    floor like `surfaced` does.

    The floor is a ledger fact. Nothing the room says reads it; what does is
    `session_is_done` — the `done` a turn answers with, and the stamp progression follows.
    The release never reads it (ADR 0037). Biased against completing hollow: anything
    unknown counts as not met.
    """
    merged = {**initial_state(pericope_num), **state}
    for element in elements_for(pericope_num):
        bar = (
            CoverageStatus.SURFACED
            if element.kind.value in _EXITS_AT_SURFACED
            else CoverageStatus.ENGAGED
        )
        standing = CoverageStatus(merged.get(element.key, CoverageStatus.NOT_ENCOUNTERED))
        if _RANK[standing] < _RANK[bar]:
            return False
    return True


def absence_positions(pericope_num: str) -> list[int]:
    return [
        index
        for index, element in enumerate(elements_for(pericope_num))
        if element.kind is ElementKind.ABSENCE
    ]
