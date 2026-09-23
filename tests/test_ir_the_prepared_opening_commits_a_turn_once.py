"""The prepared opening's own turn, counted the way `test_ir_a_voiced_turn_commits_once.py`
counts the voiced one: at the engine, by the `commit` event, never by reading the code back.

`take_prepared` and `remember_turn` are ENG-1021's own shape already; what was still open was
whether this branch of `_answer_the_turn` asked for the single landing UPDATE once or three
times — once to consume the line, once to write the exchange, once to remember the turn id.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine as app_engine
from app.services.internalization_room.sessions import create_session, get_session
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client

P = "P03"
PREPARED = "Vamos ficar nesta parte."


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as c:
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
