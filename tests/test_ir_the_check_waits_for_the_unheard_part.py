"""The check waits while a part of the rehearsal is still unheard.

The analyst reads the telling-back against the map and the room voices what is missing from
it. Over a part nobody played, that sentence is about audio the team never heard — and the
reading that produced it is a reading of a passage they were still walking through. So the
room refuses the check before the analyst is called, names the parts that are unheard, says
so in her own words, and spends nothing: no turn, no reading, no line in the conversation.

It is the untold stretch's errand, one step later: told back is not the same as heard, and
the two are asked in the order the team is already walking — untold first, unheard second.

These cases describe what the room answers and what it did not spend. They read the stored
state only where the subject is precisely that nothing advanced.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.segments import divide_segment
from app.services.internalization_room.sessions import get_session
from tests.room_harness import (
    Analyst,
    Room,
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    stretch_on,
    the_analyst_reads,
    the_room_speaks,
)

#: Her P-unheard line, pinned from the ticket and not read back out of the file that
#: carries it: the case is that the team hears *this sentence*, and a copy of whatever
#: the room happens to say would agree with any of them.
UNHEARD_LINE = "Ainda falta ouvir um trecho da gravação antes de eu conferir."
PART_MS = 61000


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _transcript(db: AsyncSession, session_id: str) -> list[Any]:
    return list((await get_session(db, session_id)).messages or [])


@pytest.mark.asyncio
async def test_a_part_the_team_never_played_refuses_the_check_and_names_it(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
    room: Room,
) -> None:
    """The rule. A part nobody played is named, her line is said, and nothing is spent.

    The analyst is not asked, because what it would answer is a list of what is missing from
    a passage the team has not finished listening to — and the room would voice it as if the
    work were done.
    """
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    before = await _transcript(db_session, session.id)
    was = await stored_telling_back(db_session, session)

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, second.id])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["unheard_take_ids"] == [third.id]
    assert body["checked"] is False
    assert body["fixed_line"] == ""
    assert body["findings_remaining"] == 0
    assert body["untold_segment_id"] is None
    assert body["audio_url"] != ""
    assert room.said == [UNHEARD_LINE]
    assert analyst.readings == 0

    stored = await stored_telling_back(db_session, session)
    assert stored.waited == was.waited, "the waiting line is the untold errand's ladder"
    assert stored.analysed_segment_ids == was.analysed_segment_ids
    assert stored.checked == was.checked
    assert await _transcript(db_session, session.id) == before


@pytest.mark.asyncio
async def test_the_third_part_played_reaches_the_verdict_on_one_analyst_call(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """The refusal costs the reading nothing: the press that hears it all pays for one.

    The transcript growing here is what makes the silence in the case above a measurement
    and not an accident of where the exchange is written.
    """
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    refused = await press_terminei(
        client, session.id, report=played_every_part([first.id, second.id])
    )
    assert refused.status_code == 200, refused.text
    before = await _transcript(db_session, session.id)

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, second.id, third.id])
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["unheard_take_ids"] == []
    assert analyst.readings == 1, "the refused press did not buy a reading"
    assert len(await _transcript(db_session, session.id)) > len(before)


@pytest.mark.asyncio
async def test_an_untold_stretch_is_the_first_errand(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """A team that owes both errands is sent on the one they were already walking.

    The untold stretch is the older errand and its line rotates on a counter of its own, so
    the two must not be served together and the ladder must not be walked for the other
    reason.
    """
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    await divide_segment(
        db_session, session, await stretch_on(db_session, session, third), at_ms=PART_MS // 2
    )

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, second.id])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["untold_segment_id"] is not None
    assert body["unheard_take_ids"] == []
    assert analyst.readings == 0
    assert (await stored_telling_back(db_session, session)).waited == 1


@pytest.mark.asyncio
async def test_a_second_press_serves_the_stored_verdict_without_re_checking(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """The gate does not turn a repeat press back into a reading the team already paid for."""
    session, parts = await rehearsed_in_parts(db_session, 3)
    report = played_every_part([part.id for part in parts])

    first = await press_terminei(client, session.id, report=report)
    again = await press_terminei(client, session.id, report=report)

    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    assert again.json() == first.json()
    assert analyst.readings == 1


@pytest.mark.asyncio
async def test_a_report_about_a_recording_no_stretch_names_is_ignored(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """An entry about audio no stretch is a slice of any more neither confirms nor refuses.

    It is the residue of a part the team recorded again, and refusing on it would refuse a
    rehearsal that was in fact heard whole.
    """
    session, parts = await rehearsed_in_parts(db_session, 3)
    report = played_every_part([part.id for part in parts] + ["uma-gravacao-que-ninguem-nomeia"])

    answered = await press_terminei(client, session.id, report=report)

    assert answered.status_code == 200, answered.text
    assert answered.json()["unheard_take_ids"] == []
    assert analyst.readings == 1


@pytest.mark.asyncio
async def test_a_flat_report_or_none_is_refused_with_every_part_named(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
    room: Room,
) -> None:
    """Numbers with no subject, and silence, say the same thing about the parts: nothing.

    The flat pair is the record of what an older build reported and it is evidence of
    nothing, so the team is sent to play the rehearsal through on a build that names the
    parts (ADR 0017). A press with no body at all says even less.
    """
    session, parts = await rehearsed_in_parts(db_session, 3)
    every_part = sorted(part.id for part in parts)
    glued = PART_MS * len(parts)

    flat = await press_terminei(
        client, session.id, report={"played_ranges": [[0, glued]], "clip_duration_ms": glued}
    )
    silent = await press_terminei(client, session.id)

    assert flat.status_code == 200, flat.text
    assert silent.status_code == 200, silent.text
    assert flat.json()["unheard_take_ids"] == every_part
    assert silent.json()["unheard_take_ids"] == every_part
    assert room.said == [UNHEARD_LINE, UNHEARD_LINE]
    assert analyst.readings == 0


@pytest.mark.asyncio
async def test_a_malformed_span_is_refused_at_the_door(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A span is two numbers. One that is not is refused where it arrives, not at the release.

    Stored, it made every release attempt a 500: the covering arithmetic unpacks each span as
    a start and an end, and a report the team can no longer change was enough to strand the
    package for good.
    """
    session, parts = await rehearsed_in_parts(db_session, 3)
    honest = played_every_part([part.id for part in parts])
    assert (await press_terminei(client, session.id, report=honest)).status_code == 200
    kept = [
        entry.model_dump(mode="json")
        for entry in (await stored_telling_back(db_session, session)).played_by_take
    ]

    refused = [
        await press_terminei(
            client,
            session.id,
            report={
                "played_by_take": [
                    {"take_id": parts[0].id, "played_ranges": spans, "clip_duration_ms": PART_MS}
                ]
            },
        )
        for spans in ([[0]], [[]], [[0, 1, 2]])
    ]
    flat = await press_terminei(
        client, session.id, report={"played_ranges": [[0, 1, 2]], "clip_duration_ms": PART_MS}
    )

    assert [answered.status_code for answered in refused] == [422, 422, 422]
    assert flat.status_code == 422, flat.text
    assert [
        entry.model_dump(mode="json")
        for entry in (await stored_telling_back(db_session, session)).played_by_take
    ] == kept
