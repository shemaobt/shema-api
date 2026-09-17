"""The fourth status is no longer written, and the rows that carry it are still read.

`partially_engaged` went into `ir_coverage_events` from 28 August (f30c8ee) until the room
stopped writing it. Dropping the value would make every one of those rows a `ValueError`
in `furthest` and `floor_met`, or — through the `else_=0` of the SQL `CASE` that teaches
the scale to the database — a bead that reads as never touched. So the word stays on the
scale as a legacy value, above `not_encountered` and no higher than `surfaced`: the team
took it up on the Guide's terms, which in her design is exactly what `surfaced` means.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import (
    CoverageStatus,
    counts,
    floor_met,
    furthest,
    initial_state,
    merge,
    ranks,
)
from app.services.internalization_room.coverage_events import necklace_of

P = "P03"
NOT_ENCOUNTERED = CoverageStatus.NOT_ENCOUNTERED.value
SURFACED = CoverageStatus.SURFACED.value
PARTIALLY_ENGAGED = CoverageStatus.PARTIALLY_ENGAGED.value
ENGAGED = CoverageStatus.ENGAGED.value


def test_the_legacy_value_ranks_above_nothing_and_no_higher_than_surfaced() -> None:
    scale = ranks()

    assert scale[NOT_ENCOUNTERED] < scale[PARTIALLY_ENGAGED] <= scale[SURFACED] < scale[ENGAGED]


@pytest.mark.asyncio
async def test_a_stored_partial_bead_is_read_back_and_still_holds_the_floor(
    db_session: AsyncSession,
) -> None:
    keys = element_keys(P)
    legacy, *worked = keys
    session = await room.create_session(db_session, pericope=P)
    await room.apply_coverage(
        db_session,
        session.id,
        {**dict.fromkeys(worked, ENGAGED), legacy: PARTIALLY_ENGAGED},
    )

    read_back = await necklace_of(db_session, session)

    assert read_back[legacy] == PARTIALLY_ENGAGED, (
        "a linha antiga voltava do banco como not_encountered pelo else_=0 do CASE"
    )
    assert floor_met(read_back, P) is False, (
        "o piso descia até a conta ecoada e a passagem fechava em cima dela"
    )
    assert counts(read_back) == {"engaged": len(worked), "surfaced": len(keys), "total": len(keys)}


def test_the_legacy_value_still_moves_forward_and_never_back() -> None:
    key = element_keys(P)[0]
    legacy = {**initial_state(P), key: PARTIALLY_ENGAGED}

    assert merge(legacy, pericope_num=P, engaged=[key])[key] == ENGAGED
    assert furthest(legacy, {key: NOT_ENCOUNTERED}, pericope_num=P)[key] == PARTIALLY_ENGAGED
    assert furthest({key: ENGAGED}, legacy, pericope_num=P)[key] == ENGAGED
