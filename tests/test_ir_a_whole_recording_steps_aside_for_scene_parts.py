"""ENG-1406 — a whole recording is current only while no numbered part exists.

Before 19 Aug a team recorded the passage in one go: one rehearsal take with no number. Once
the same session holds a numbered part, that whole is history — kept with its stretches and
findings, never deleted, and no longer asked for by `terminei` or carried by the release.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.services.internalization_room.back_translation import (
    Finding,
    FindingKind,
)
from app.services.internalization_room.release import approve_release
from app.services.internalization_room.sessions import get_session, save_back_translation
from app.services.internalization_room.takes import current_parts, takes_of
from tests.room_harness import (
    Analyst,
    Room,
    a_piece_still_to_be_told,
    played_every_part,
    press_terminei,
    rehearsed_in_parts_of,
    release_packet,
    room_client,
    stored_telling_back,
    the_analyst_reads,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

PART_LENGTH_MS = 2000


def _heard(parts: list[IRTake]) -> dict[str, Any]:
    return played_every_part([part.id for part in parts], duration_ms=PART_LENGTH_MS)


async def _stored_stretches(db: AsyncSession, session: IRSession) -> list[IRSegment]:
    rows = await db.execute(select(IRSegment).where(IRSegment.session_id == session.id))
    return list(rows.scalars().all())


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
        report=_heard(parts),
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
        report=_heard(parts),
    )
    assert checked.json()["checked"] is True, checked.text

    packet = await release_packet(db_session, session)

    assert [take["take_id"] for take in packet["audio"]["rehearsal_takes"]] == [
        part.id for part in parts
    ]
    assert packet["audio"]["recording_grain"] == "parts"


async def test_the_analyst_reads_no_frase_told_over_a_whole_that_stepped_aside(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    readings: list[str] = []

    async def reading(*, system_prompt: str, user_content: str, **_: Any) -> str:
        readings.append(f"{system_prompt}\n{user_content}")
        return '{"evidence_sufficient": true, "findings": []}'

    the_room_agent_is(monkeypatch, analyst=reading)
    session, _whole, parts = await _whole_then_two_parts(db_session)

    await press_terminei(client, session.id, report=_heard(parts))

    [read] = readings
    assert "a frase 3, contada de volta" in read
    assert "a frase 1, contada de volta" not in read
    assert "a frase 2, contada de volta" not in read


async def test_an_untold_stretch_of_a_whole_that_stepped_aside_does_not_block_the_finish(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, whole, parts = await _whole_then_two_parts(db_session)
    [first, *_] = [s for s in await _stored_stretches(db_session, session) if s.take_id == whole.id]
    await a_piece_still_to_be_told(db_session, await get_session(db_session, session.id), first)

    answered = await press_terminei(client, session.id, report=_heard(parts))

    assert answered.status_code == 200, answered.text
    assert answered.json()["refusal"] is None
    assert answered.json()["untold_segment_id"] is None


async def test_the_packet_carries_no_stretch_of_a_whole_that_stepped_aside(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _whole, parts = await _whole_then_two_parts(db_session)
    await press_terminei(client, session.id, report=_heard(parts))

    packet = await release_packet(db_session, session)

    carried = {s["take_id"] for s in packet["back_translation"]["segments"]}
    assert carried == {part.id for part in parts}


async def test_the_stretches_of_a_whole_that_stepped_aside_are_still_stored(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, whole, parts = await _whole_then_two_parts(db_session)
    await press_terminei(client, session.id, report=_heard(parts))

    stored = await _stored_stretches(db_session, session)

    assert len([s for s in stored if s.take_id == whole.id]) == 2


async def test_a_finding_on_a_whole_that_stepped_aside_leaves_the_packet_and_stays_stored(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, whole, parts = await _whole_then_two_parts(db_session)
    await press_terminei(client, session.id, report=_heard(parts))
    [over_whole, *_] = [
        s for s in await _stored_stretches(db_session, session) if s.take_id == whole.id
    ]
    state = await stored_telling_back(db_session, session)
    state.findings = [
        Finding(kind=FindingKind.MISSING, note="faltou Moabe", segment_id=over_whole.id, chunk=1)
    ]
    await save_back_translation(db_session, await get_session(db_session, session.id), state)

    packet = await release_packet(db_session, session)

    assert packet["back_translation"]["findings"] == []
    assert [f.segment_id for f in (await stored_telling_back(db_session, session)).findings] == [
        over_whole.id
    ]


async def _with_a_finding_on_the_whole(
    client: httpx.AsyncClient, db: AsyncSession
) -> tuple[IRSession, IRSegment, list[IRTake]]:
    session, whole, parts = await _whole_then_two_parts(db)
    await press_terminei(client, session.id, report=_heard(parts))
    [over_whole, *_] = [s for s in await _stored_stretches(db, session) if s.take_id == whole.id]
    state = await stored_telling_back(db, session)
    state.findings = [
        Finding(kind=FindingKind.MISSING, note="faltou Moabe", segment_id=over_whole.id, chunk=1)
    ]
    await save_back_translation(db, await get_session(db, session.id), state)
    return session, over_whole, parts


async def test_a_forced_release_does_not_record_a_finding_on_a_whole_that_stepped_aside(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _over_whole, _parts = await _with_a_finding_on_the_whole(client, db_session)

    release = await approve_release(
        db_session, await get_session(db_session, session.id), forced_by="a-facilitadora"
    )

    assert release.forced_open_findings == []


async def test_terminei_is_not_refused_by_a_stored_verdict_whose_finding_is_on_the_whole(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _over_whole, parts = await _with_a_finding_on_the_whole(client, db_session)

    answered = await press_terminei(client, session.id, report=_heard(parts))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] is None
    assert body["finding_segment_id"] is None
    assert body["findings"] == []
