from __future__ import annotations

import enum
from collections.abc import Iterable

from app.services.internalization_room.canon.elements import (
    Element,
    ElementKind,
    element_keys,
    elements_for,
)


class CoverageStatus(enum.StrEnum):
    NOT_ENCOUNTERED = "not_encountered"
    SURFACED = "surfaced"
    PARTIALLY_ENGAGED = "partially_engaged"
    ENGAGED = "engaged"


_RANK = {
    CoverageStatus.NOT_ENCOUNTERED: 0,
    CoverageStatus.SURFACED: 1,
    CoverageStatus.PARTIALLY_ENGAGED: 2,
    CoverageStatus.ENGAGED: 3,
}


def initial_state(pericope_num: str) -> dict[str, str]:
    return dict.fromkeys(element_keys(pericope_num), CoverageStatus.NOT_ENCOUNTERED.value)


def merge(
    state: dict[str, str],
    *,
    pericope_num: str,
    surfaced: Iterable[str] = (),
    partially_engaged: Iterable[str] = (),
    engaged: Iterable[str] = (),
) -> dict[str, str]:
    """Advance coverage. Movement is one-way: a status never drops back.

    An element named in more than one bucket lands on the furthest of them, whatever order
    the classifier listed it in — each step only moves forward.
    """
    merged = {**initial_state(pericope_num), **state}
    buckets = (
        (surfaced, CoverageStatus.SURFACED),
        (partially_engaged, CoverageStatus.PARTIALLY_ENGAGED),
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
    "encountered at least" figure and so takes in the partly worked ones too. Because the
    completion floor now admits `partially_engaged`, a session can reach `done` with
    `engaged` short of `total` — visible to the facilitator, and the coverage route's to
    render.
    """
    engaged = sum(1 for value in state.values() if value == CoverageStatus.ENGAGED)
    encountered = (
        CoverageStatus.SURFACED,
        CoverageStatus.PARTIALLY_ENGAGED,
        CoverageStatus.ENGAGED,
    )
    surfaced = sum(1 for value in state.values() if value in encountered)
    return {"engaged": engaged, "surfaced": surfaced, "total": len(state)}


def remaining(state: dict[str, str], pericope_num: str) -> list[Element]:
    """What the team has not worked yet, with labels the Guide can act on.

    A partly worked element stays on this list even though it satisfies the completion
    floor: the floor being met is not the same as the work being finished. It is also the
    only way the element can still be promoted — the classifier is shown this list and
    nothing else, so a bead dropped from it is frozen at whatever status it left with.
    """
    merged = {**initial_state(pericope_num), **state}
    return [
        element
        for element in elements_for(pericope_num)
        if merged.get(element.key) != CoverageStatus.ENGAGED
    ]


def floor_met(state: dict[str, str], pericope_num: str) -> bool:
    """Every element worked with, at least in part.

    The design document lets only the four abstract Level-1 axes exit at `surfaced`; the maps
    expose no such elements, so every bead here is concrete and none is exempt. What the floor
    does not demand is the strong reading of every one of them. A passage's preservation rules
    are engaged by noticing a silence, which mostly reaches the room as the team taking up the
    Guide's noticing rather than arriving at it themselves; requiring the unprompted version
    from all five of Ruth 1's is how a passage becomes one that never closes. Since `done` is
    what moves a team on to the next passage, a floor that cannot be reached does not hold a
    team to a higher standard — it holds them still.

    `surfaced` remains below the floor, so a session where the Guide did the talking still
    cannot complete. Biased against completing hollow: anything unknown counts as not met.
    """
    merged = {**initial_state(pericope_num), **state}
    for element in elements_for(pericope_num):
        standing = CoverageStatus(merged.get(element.key, CoverageStatus.NOT_ENCOUNTERED))
        if _RANK[standing] < _RANK[CoverageStatus.PARTIALLY_ENGAGED]:
            return False
    return True


def absence_positions(pericope_num: str) -> list[int]:
    return [
        index
        for index, element in enumerate(elements_for(pericope_num))
        if element.kind is ElementKind.ABSENCE
    ]
