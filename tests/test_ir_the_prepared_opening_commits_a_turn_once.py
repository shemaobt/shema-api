"""The prepared opening's own turn, counted the way `test_ir_a_voiced_turn_commits_once.py`
counts the voiced one: at the engine, by the `commit` event, never by reading the code back.

`take_prepared` and `remember_turn` are ENG-1021's own shape already; what was still open was
whether this branch of `_answer_the_turn` asked for the single landing UPDATE once or three
times — once to consume the line, once to write the exchange, once to remember the turn id.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine as app_engine
from app.services.internalization_room.sessions import create_session, get_session
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client

P = "P03"
PREPARED = "Vamos ficar nesta parte."


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
async def per_request_client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, test_engine: object
) -> AsyncIterator[httpx.AsyncClient]:
    """The room over HTTP the way it is deployed: every request through its own session.

    The shared ``db_session`` client above cannot show two requests racing the same row —
    every call would share one connection's identity map, which hides the race entirely
    (the same reason ``rival_factory`` exists in ``test_ir_session_version_conflict.py``).
    """
    per_request = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
def commits(test_engine) -> Iterator[list[object]]:
    counted: list[object] = []

    def _count(connection: object) -> None:
        counted.append(connection)

    engines = (test_engine.sync_engine, app_engine.sync_engine)
    for each in engines:
        event.listen(each, "commit", _count)
    try:
        yield counted
    finally:
        for each in engines:
            event.remove(each, "commit", _count)


async def _a_session_with_a_line_ready(db_session: AsyncSession) -> str:
    """What the background preparation leaves behind when it wins the race (ENG-1034)."""
    session = await create_session(db_session, language="pt", pericope=P)
    parked = await get_session(db_session, session.id)
    parked.prepared_speech = PREPARED
    parked.prepared_audio_key = "tts/voice/m/f/prepared.mp3"
    parked.prepared_pericope = P
    await db_session.commit()
    return session.id


async def test_a_prepared_opening_with_a_turn_id_reaches_the_database_in_one_commit(
    db_session: AsyncSession, client: httpx.AsyncClient, commits: list[object]
) -> None:
    session_id = await _a_session_with_a_line_ready(db_session)
    commits.clear()

    opened = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        data={"turn_id": "abertura-1"},
    )

    assert opened.status_code == 200, opened.text[:300]
    assert len(commits) == 1, (
        "a abertura preparada gravava o consumo da linha, a troca e a lembrança do turno em"
        " três commits"
    )


async def test_a_prepared_opening_with_no_turn_id_also_reaches_the_database_in_one_commit(
    db_session: AsyncSession, client: httpx.AsyncClient, commits: list[object]
) -> None:
    session_id = await _a_session_with_a_line_ready(db_session)
    commits.clear()

    opened = await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, opened.text[:300]
    assert len(commits) == 1, (
        "sem turn_id o commit final ficava dentro do `if turn_id:` e o ramo não comitava"
        " nada no fim — só o consumo da linha e a troca, cada um por conta própria"
    )


async def test_two_requests_racing_the_same_prepared_opening_leave_only_the_winners_commit(
    db_session: AsyncSession,
    per_request_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    commits: list[object],
) -> None:
    """A second reader loses the version guard `append_exchange` already carries either way —
    what the single shared transaction changes is whether *its own* consumption of the line
    still lands. Counting commits, not just the final row, is what tells the two apart: a
    prepared opening's read is not guarded by anything of its own, so before this fix the
    loser's own `take_prepared` committed unconditionally, on its own, before its exchange
    ever hit the version conflict that undid the rest of its turn.
    """
    session_id = await _a_session_with_a_line_ready(db_session)
    commits.clear()

    from app.api.internalization_room import sessions as sessions_api

    real_take_prepared = sessions_api.take_prepared
    fired = False

    async def take_prepared_but_a_rival_reads_the_line_first(
        *args: Any, **kwargs: Any
    ) -> tuple[str, str] | None:
        nonlocal fired
        if not fired:
            fired = True
            rival = await per_request_client.post(
                f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY}
            )
            assert rival.status_code == 200, rival.text[:300]
        return await real_take_prepared(*args, **kwargs)

    monkeypatch.setattr(
        sessions_api, "take_prepared", take_prepared_but_a_rival_reads_the_line_first
    )

    lost = await per_request_client.post(
        f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY}
    )

    assert lost.status_code == 409, lost.text[:300]
    assert len(commits) == 1, (
        "o pedido que perdeu a corrida comitava sozinho o consumo da linha antes de perder"
        " a troca no guarda de version — a linha era tomada duas vezes, uma delas sem troca"
    )
