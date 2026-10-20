"""ENG-1406 — a whole recording is current only while no numbered part exists.

Before 19 Aug a team recorded the passage in one go: one rehearsal take with no number. Once
the same session holds a numbered part, that whole is history — kept with its stretches and
findings, never deleted, and no longer asked for by `terminei` or carried by the release.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.takes import current_parts, takes_of
from tests.room_harness import (
    Analyst,
    Room,
    played_every_part,
    press_terminei,
    rehearsed_in_parts_of,
    release_packet,
    room_client,
    stored_telling_back,
    the_analyst_reads,
    the_room_speaks,
)

PART_LENGTH_MS = 2000


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


async def _whole_then_two_parts(db: AsyncSession) -> tuple[IRSession, IRTake, list[IRTake]]:
    session, (whole, *parts) = await rehearsed_in_parts_of(db, [2, 2, 2], unnumbered_first=True)
    return session, whole, parts


async def test_a_whole_recording_alone_is_the_sessions_current_part(
    db_session: AsyncSession,
) -> None:
    session, (whole,) = await rehearsed_in_parts_of(db_session, [2], told_whole=True)

    current = current_parts(await takes_of(db_session, session.id))

    assert [part.id for part in current] == [whole.id]


async def test_a_whole_recording_steps_aside_the_moment_a_numbered_part_lands(
    db_session: AsyncSession,
) -> None:
    session, whole, parts = await _whole_then_two_parts(db_session)

    takes = await takes_of(db_session, session.id)

    assert [part.id for part in current_parts(takes)] == [part.id for part in parts]
    assert whole.id in {take.id for take in takes}, "a gravação inteira foi apagada"


async def test_terminei_does_not_ask_for_a_whole_that_stepped_aside(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _whole, parts = await _whole_then_two_parts(db_session)

    answered = await press_terminei(
        client,
        session.id,
        report=played_every_part([part.id for part in parts], duration_ms=PART_LENGTH_MS),
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] is None
    assert body["unheard_take_ids"] == []


async def test_the_release_does_not_carry_a_whole_that_stepped_aside(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _whole, parts = await _whole_then_two_parts(db_session)
    checked = await press_terminei(
        client,
        session.id,
        report=played_every_part([part.id for part in parts], duration_ms=PART_LENGTH_MS),
    )
    assert checked.json()["checked"] is True, checked.text

    packet = await release_packet(db_session, session)

    assert [take["take_id"] for take in packet["audio"]["rehearsal_takes"]] == [
        part.id for part in parts
    ]
    assert packet["audio"]["recording_grain"] == "parts"


async def test_a_wholes_stretches_and_findings_are_kept_when_it_steps_aside(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, whole, parts = await _whole_then_two_parts(db_session)
    await press_terminei(
        client,
        session.id,
        report=played_every_part([part.id for part in parts], duration_ms=PART_LENGTH_MS),
    )

    packet = await release_packet(db_session, session)

    kept = [s for s in await final_segments(db_session, session.id) if s.take_id == whole.id]
    assert len(kept) == 2, "as frases da gravação inteira saíram do registro"
    carried = [s for s in packet["back_translation"]["segments"] if s["take_id"] == whole.id]
    assert len(carried) == 2, "as frases da gravação inteira não viajam com o registro"
    assert (await stored_telling_back(db_session, session)).checked is True
