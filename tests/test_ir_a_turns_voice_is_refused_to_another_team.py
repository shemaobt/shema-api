from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import create_session
from tests.clip_flight_harness import (
    GUIDE_LINE,
    Elevenlabs,
    WriteOnceBucket,
    another_instance,
    voice_room_client,
)
from tests.release_harness import PREFIX, a_claimed_device, team_headers


@pytest.fixture()
def elevenlabs() -> Elevenlabs:
    return Elevenlabs(b"the rendering")


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, elevenlabs: Elevenlabs):
    from app.api.internalization_room import sessions as sessions_api

    async def _opening(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=GUIDE_LINE, transcript="")

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _opening)
    async with voice_room_client(
        db_session, monkeypatch, elevenlabs=elevenlabs, bucket=WriteOnceBucket()
    ) as c:
        yield c


@pytest.fixture()
async def teams(db_session: AsyncSession) -> tuple[IRSession, dict[str, str], dict[str, str]]:
    ours, our_credential = await a_claimed_device(db_session, email="nossa@example.com")
    theirs, their_credential = await a_claimed_device(db_session, email="outra@example.com")
    session = await create_session(db_session, language="pt", pericope="OV", project_id=ours.id)
    await create_session(db_session, language="pt", pericope="OV", project_id=theirs.id)
    return session, team_headers(our_credential), team_headers(their_credential)


async def _their_own_session(db_session: AsyncSession, session: IRSession) -> str:
    from sqlalchemy import select

    rows = await db_session.execute(select(IRSession.id).where(IRSession.id != session.id))
    return rows.scalar_one()


async def test_another_teams_tablet_never_makes_this_sessions_line_speak(
    client: httpx.AsyncClient,
    elevenlabs: Elevenlabs,
    teams: tuple[IRSession, dict[str, str], dict[str, str]],
) -> None:
    session, ours, theirs = teams
    elevenlabs.failures = 1
    answered = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers=ours)
    await asyncio.sleep(0.05)
    another_instance()

    heard = await client.get(answered.json()["audio_url"], headers=theirs)

    assert heard.status_code == 404
    assert elevenlabs.texts == [GUIDE_LINE], (
        "um tablet de outra equipe fazia o servidor sintetizar uma fala da sessão alheia"
    )


async def test_another_teams_tablet_is_refused_before_the_line_being_voiced_reaches_it(
    client: httpx.AsyncClient,
    elevenlabs: Elevenlabs,
    teams: tuple[IRSession, dict[str, str], dict[str, str]],
) -> None:
    session, ours, theirs = teams
    elevenlabs.held.clear()
    answered = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers=ours)
    listening = asyncio.create_task(client.get(answered.json()["audio_url"], headers=theirs))
    await asyncio.sleep(0.05)
    elevenlabs.held.set()
    heard = await asyncio.wait_for(listening, timeout=1)

    assert heard.status_code == 404
    assert b"the rendering" not in heard.content, (
        "o GET de outra equipe entrava na síntese em voo e recebia a fala da sessão alheia"
    )


async def test_another_teams_tablet_naming_its_own_session_still_never_hears_this_line(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    teams: tuple[IRSession, dict[str, str], dict[str, str]],
) -> None:
    session, ours, theirs = teams
    answered = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers=ours)
    await asyncio.sleep(0.05)
    handle = answered.json()["audio_url"].rsplit("/", 1)[-1]
    their_session = await _their_own_session(db_session, session)

    heard = await client.get(f"{PREFIX}/voice/{their_session}/{handle}", headers=theirs)

    assert heard.status_code == 404, (
        "a rota conferia o dono da sessão na URL, mas não que a fala era dela: outra equipe "
        "punha a própria sessão e o nosso handle e recebia a nossa fala"
    )
    assert b"the rendering" not in heard.content


async def test_the_team_that_owns_the_line_still_hears_it_from_another_instance(
    client: httpx.AsyncClient,
    elevenlabs: Elevenlabs,
    teams: tuple[IRSession, dict[str, str], dict[str, str]],
) -> None:
    session, ours, _ = teams
    elevenlabs.failures = 1
    answered = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers=ours)
    await asyncio.sleep(0.05)
    another_instance()

    heard = await client.get(answered.json()["audio_url"], headers=ours)

    assert heard.status_code == 200
    assert heard.content == b"the rendering"


async def test_the_handle_route_never_joins_a_turns_line_being_voiced(
    client: httpx.AsyncClient,
    elevenlabs: Elevenlabs,
    teams: tuple[IRSession, dict[str, str], dict[str, str]],
) -> None:
    session, ours, theirs = teams
    elevenlabs.held.clear()
    answered = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers=ours)
    handle = answered.json()["audio_url"].rsplit("/", 1)[-1]
    listening = asyncio.create_task(client.get(f"{PREFIX}/voice/{handle}", headers=theirs))
    await asyncio.sleep(0.05)
    elevenlabs.held.set()
    heard = await asyncio.wait_for(listening, timeout=1)

    assert heard.status_code == 404, (
        "a rota sem sessão se juntava à síntese em voo e entregava a fala do turno a quem "
        "tivesse o handle, sem saber de que sessão ela era"
    )
