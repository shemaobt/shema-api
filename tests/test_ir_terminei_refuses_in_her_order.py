"""ENG-1197 — `terminei` reaches the check only on her conditions, and refuses in her order.

Her check (bt/check/route.ts:64-78 at her freeze) refuses a frase awaiting its translation
first, then a part not yet heard, then, on a joined recording, a stretch nothing translates,
and last a passage with nothing translated at all. Each refusal is a code the tablet turns into
her screen line; none of them asks the analyst or saves anything.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.sessions import create_session, get_session
from tests.device_harness import TABLET_TEAM
from tests.release_harness import P
from tests.room_harness import (
    Analyst,
    Room,
    another_rehearsal_take,
    played_every_part,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    the_analyst_reads,
    the_room_speaks,
)


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


async def _recorded_and_never_translated(
    db: AsyncSession, parts: int
) -> tuple[IRSession, list[IRTake]]:
    session = await create_session(db, pericope=P, project_id=TABLET_TEAM, language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await db.commit()
    takes = [
        await another_rehearsal_take(
            db,
            session,
            sha256=chr(ord("a") + index) * 64,
            scope=f"parte-{index + 1}",
            ordinal=index + 1,
        )
        for index in range(parts)
    ]
    return session, takes


async def _transcript(db: AsyncSession, session_id: str) -> list[Any]:
    return list((await get_session(db, session_id)).messages or [])


@pytest.mark.parametrize("recorded", [0, 2], ids=["nothing recorded", "two parts recorded"])
async def test_a_recording_heard_through_with_no_frase_translated_is_refused_in_silence(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst, room: Room, recorded: int
) -> None:
    session, parts = await _recorded_and_never_translated(db_session, recorded)
    was = await stored_telling_back(db_session, session)

    answered = await press_terminei(
        client, session.id, report=played_every_part([part.id for part in parts])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "NOTHING_TRANSLATED"
    assert body["checked"] is False
    assert body["audio_url"] == "", "ela só mostra «ainda não tem frase traduzida», sem voz"
    assert body["fixed_line"] == "", "o D-1 dizia que a sala não ouviu, e nada foi dito"
    assert room.said == []
    assert analyst.readings == 0
    assert await _transcript(db_session, session.id) == []
    assert (await stored_telling_back(db_session, session)).waited == was.waited


async def test_a_part_heard_with_nothing_translated_over_it_is_read_with_the_rest_not_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3)
    fresh = await record_the_part_again(db_session, session, second, sha256="d" * 64)

    answered = await press_terminei(
        client, session.id, report=played_every_part([first.id, fresh.id, third.id])
    )

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] is None
    assert analyst.readings == 1, "nela a checagem roda e o Analista nomeia o que falta"
    assert body["audio_url"] != ""
