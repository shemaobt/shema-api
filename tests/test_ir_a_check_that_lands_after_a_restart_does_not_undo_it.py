from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.internalization_room import verdict_round
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    start_the_translation_over,
)
from tests.release_harness import a_claimed_device, team_headers
from tests.room_harness import (
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_is_scripted,
    the_room_speaks,
)
from tests.turn_harness import the_room_agent_is

SAID = "Vocês contaram bem."
ON_FRASE_2 = {
    "kind": "nuance",
    "note": "O jeito de contar mudou.",
    "frase": 2,
    "quote": "contada de volta",
    "story": "a história conta de outro jeito",
}


class Speaker:
    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return SAID


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_a_check_that_read_before_a_restart_and_lands_after_it_goes_to_the_archive(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker())
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, _ = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    report = await heard_every_part(db_session, session.id)
    written = verdict_round.append_exchange

    async def written_after_a_restart(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as restarting_db:
            await start_the_translation_over(
                restarting_db, await get_session(restarting_db, session.id)
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_restart)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert (stored.checks, stored.nuances) == ([], []), (
        "a conferência que leu antes do recomeço trazia a sua rodada e o seu detalhe de volta"
    )
    assert (stored.checked, stored.checked_at, stored.analysed_segment_ids) == (
        False,
        None,
        None,
    ), "a passagem recomeçada voltava a dizer que tinha sido lida"
    assert [one.spoken for one in stored.superseded[-1].checks] == [SAID], (
        "a rodada que chegou depois do recomeço sumia em vez de ir para o arquivo"
    )


async def test_a_missing_with_no_address_read_before_a_restart_goes_to_the_archive_too(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    analyst.readings = [{"findings": [{"kind": "missing", "note": "Orfa não apareceu."}]}]
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker())
    project, credential = await a_claimed_device(db_session)
    client.headers.update(team_headers(credential))
    session, _ = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    report = await heard_every_part(db_session, session.id)
    written = verdict_round.append_exchange

    async def written_after_a_restart(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as restarting_db:
            await start_the_translation_over(
                restarting_db, await get_session(restarting_db, session.id)
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_restart)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert stored.findings == [], (
        "o que faltou, sem frase, ficava de pé na passagem recomeçada e a sala o dizia sobre "
        "uma leitura sem frase nenhuma"
    )
    assert [one.note for one in stored.superseded[-1].findings] == ["Orfa não apareceu."], (
        "o que faltou, lido antes do recomeço, sumia em vez de ir para o arquivo"
    )
