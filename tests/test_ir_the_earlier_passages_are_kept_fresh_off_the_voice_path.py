from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.db.models.internalization_room import IRSession
from app.services.internalization_room import earlier_passages as statuses
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import get_session
from tests.hearing_harness import the_loop_clock_passes
from tests.release_harness import (
    PREFIX,
    a_claimed_device,
    ready_session,
    team_headers,
    team_release,
)
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted
from tests.text_seam_harness import ScriptedAgent

EARLIER = "EARLIER PASSAGES FOR THIS TEAM:"
NONE_WORKED = (
    "EARLIER PASSAGES FOR THIS TEAM: Not worked yet: Ruth 1:1\N{EN DASH}5, "
    "Ruth 1:6\N{EN DASH}14, Ruth 1:15\N{EN DASH}18."
)
P01_APPROVED = (
    "EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1\N{EN DASH}5. "
    "Not worked yet: Ruth 1:6\N{EN DASH}14, Ruth 1:15\N{EN DASH}18."
)


@pytest.fixture()
def agent(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    guide = ScriptedAgent([])

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belem com Rute")

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=guide)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return guide


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, agent, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def opened_on_p04(client: httpx.AsyncClient, tablet: str) -> str:
    answered = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P04"},
    )
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()["session_id"]


async def stamped(
    per_request: async_sessionmaker[AsyncSession], session_id: str, stamp: dict[str, str]
) -> None:
    async with per_request() as fresh:
        await fresh.execute(
            update(IRSession).where(IRSession.id == session_id).values(earlier_passages=stamp)
        )
        await fresh.commit()


async def stored_statuses(
    per_request: async_sessionmaker[AsyncSession], session_id: str
) -> dict[str, str] | None:
    async with per_request() as fresh:
        stamp = (await get_session(fresh, session_id)).earlier_passages
    return None if stamp is None else {key: value for key, value in stamp.items() if key != "at"}


def the_statuses_never_answer(monkeypatch: pytest.MonkeyPatch) -> asyncio.Event:
    started = asyncio.Event()

    async def never(*_: Any, **__: Any) -> dict[str, str]:
        started.set()
        await asyncio.Event().wait()
        return {}

    monkeypatch.setattr(statuses, "read_statuses", never)
    return started


async def a_turn_whose_read_never_answers(
    monkeypatch: pytest.MonkeyPatch,
    client: httpx.AsyncClient,
    tablet: str,
    session_id: str,
    while_it_reads: Any = None,
) -> None:
    started = the_statuses_never_answer(monkeypatch)
    turn = asyncio.create_task(the_room_opens(client, tablet, session_id))
    reading = asyncio.ensure_future(started.wait())
    await asyncio.wait({reading, turn}, return_when=asyncio.FIRST_COMPLETED)
    reading.cancel()
    assert not turn.done(), "o turno terminou sem que o carimbo fosse lido de novo"
    if while_it_reads is not None:
        await while_it_reads()
    the_loop_clock_passes(monkeypatch, 2.0)
    await asyncio.wait({turn}, timeout=0.3)
    assert not turn.done(), "a leitura de novo desistia antes dos 3 s dela"
    the_loop_clock_passes(monkeypatch, 1.5)
    try:
        done, _ = await asyncio.wait({turn}, timeout=5)
        assert done, "uma leitura que não respondia segurava o turno além dos 3 s dela"
    finally:
        turn.cancel()
        await asyncio.wait({turn})
    turn.result()


def read_minutes_ago(minutes: int, **statuses: str) -> dict[str, str]:
    return {**statuses, "at": (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()}


async def p01_approved(client: httpx.AsyncClient, db: AsyncSession, team: Any, tablet: str) -> None:
    p01 = await ready_session(db, pericope="P01", project_id=team.id)
    approval = await client.post(team_release(p01.id), headers=team_headers(tablet))
    assert approval.status_code == 200, approval.text[:300]


def earlier_line(system_prompt: str) -> str | None:
    lines = [line for line in system_prompt.splitlines() if line.startswith(EARLIER)]
    return lines[0] if lines else None


async def the_next_turns_line(
    client: httpx.AsyncClient, agent: ScriptedAgent, tablet: str, session_id: str
) -> str | None:
    await the_room_opens(client, tablet, session_id)
    before = len(agent.guide_systems)
    await the_team_says(client, tablet, session_id, str(uuid.uuid4()))
    return earlier_line(agent.guide_systems[before])


async def test_a_stamp_read_six_minutes_ago_is_read_again_and_the_next_turn_hears_the_approval(
    client, db_session, per_request, agent
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session_id = await opened_on_p04(client, tablet)
    await stamped(
        per_request,
        session_id,
        read_minutes_ago(6, P01="not_worked", P02="not_worked", P03="not_worked"),
    )
    await p01_approved(client, db_session, team, tablet)

    assert await the_next_turns_line(client, agent, tablet, session_id) == P01_APPROVED, (
        "um carimbo de seis minutos nunca era lido de novo, e a voz contava como não trabalhada "
        "uma passagem que a equipe já tinha aprovado"
    )


async def test_a_stamp_read_four_minutes_ago_is_not_read_again(
    client, db_session, per_request, agent
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session_id = await opened_on_p04(client, tablet)
    await stamped(
        per_request,
        session_id,
        read_minutes_ago(4, P01="not_worked", P02="not_worked", P03="not_worked"),
    )
    await p01_approved(client, db_session, team, tablet)

    assert await the_next_turns_line(client, agent, tablet, session_id) == NONE_WORKED, (
        "um carimbo de quatro minutos era lido de novo a cada turno"
    )


async def test_the_stamp_the_open_just_read_is_not_read_again_by_the_turns_after_it(
    client, db_session, agent
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session_id = await opened_on_p04(client, tablet)
    await p01_approved(client, db_session, team, tablet)

    assert await the_next_turns_line(client, agent, tablet, session_id) == NONE_WORKED, (
        "o carimbo da abertura não dizia quando foi lido, e cada turno o lia de novo"
    )


async def test_a_stamp_naming_its_unread_passages_is_read_again_on_the_next_turn(
    client, db_session, per_request, agent
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session_id = await opened_on_p04(client, tablet)
    await stamped(
        per_request,
        session_id,
        {"P01": "not_worked", "P02": "not_worked", "P03": "not_worked", "unread": "P01, P02, P03"},
    )
    await p01_approved(client, db_session, team, tablet)

    assert await the_next_turns_line(client, agent, tablet, session_id) == P01_APPROVED, (
        "um carimbo com passagens não lidas ficava assim a sessão inteira"
    )


async def test_a_read_again_that_misses_her_three_seconds_keeps_each_passages_status_and_names_it(
    client, db_session, per_request, monkeypatch
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    session_id = await opened_on_p04(client, tablet)
    await stamped(
        per_request,
        session_id,
        read_minutes_ago(6, P01="approved", P02="started", P03="not_worked"),
    )

    await a_turn_whose_read_never_answers(monkeypatch, client, tablet, session_id)

    assert await stored_statuses(per_request, session_id) == {
        "P01": "approved",
        "P02": "started",
        "P03": "not_worked",
        "unread": "P01, P02, P03",
    }, "uma leitura lenta apagava a aprovação que a sessão já conhecia"
