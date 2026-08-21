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
    ENGAGED = "engaged"


_RANK = {
    CoverageStatus.NOT_ENCOUNTERED: 0,
    CoverageStatus.SURFACED: 1,
    CoverageStatus.ENGAGED: 2,
}


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
    """Advance coverage. Movement is one-way: a status never drops back."""
    merged = {**initial_state(pericope_num), **state}
    for keys, status in ((surfaced, CoverageStatus.SURFACED), (engaged, CoverageStatus.ENGAGED)):
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
    engaged = sum(1 for value in state.values() if value == CoverageStatus.ENGAGED)
    surfaced = sum(
        1 for value in state.values() if value in (CoverageStatus.SURFACED, CoverageStatus.ENGAGED)
    )
    return {"engaged": engaged, "surfaced": surfaced, "total": len(state)}


def remaining(state: dict[str, str], pericope_num: str) -> list[Element]:
    """What the team has not worked yet, with labels the Guide can act on."""
    merged = {**initial_state(pericope_num), **state}
    return [
        element
        for element in elements_for(pericope_num)
        if merged.get(element.key) != CoverageStatus.ENGAGED
    ]


def floor_met(state: dict[str, str], pericope_num: str) -> bool:
    """Every element engaged.

    The design document lets only the four abstract Level-1 axes exit at `surfaced`; the maps
    expose no such elements, so every bead here is concrete and must be worked with. Biased
    against completing hollow: anything unknown counts as not met.
    """
    merged = {**initial_state(pericope_num), **state}
    for element in elements_for(pericope_num):
        if CoverageStatus(merged.get(element.key, CoverageStatus.NOT_ENCOUNTERED)) is not (
            CoverageStatus.ENGAGED
        ):
            return False
    return True


def absence_positions(pericope_num: str) -> list[int]:
    return [
        index
        for index, element in enumerate(elements_for(pericope_num))
        if element.kind is ElementKind.ABSENCE
    ]
