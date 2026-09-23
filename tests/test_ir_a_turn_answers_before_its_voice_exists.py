from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import clip_flight
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import append_exchange, create_session
from app.services.internalization_room.voice_handles import from_handle
from tests.clip_flight_harness import (
    GUIDE_LINE,
    Elevenlabs,
    WriteOnceBucket,
    another_instance,
    voice_room_client,
)
from tests.release_harness import PREFIX


@pytest.fixture()
def elevenlabs() -> Elevenlabs:
    return Elevenlabs(b"the rendering")


@pytest.fixture()
def bucket() -> WriteOnceBucket:
    return WriteOnceBucket()


@pytest.fixture()
async def client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: Elevenlabs,
    bucket: WriteOnceBucket,
):
    from app.api.internalization_room import sessions as sessions_api

    async def _opening(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=GUIDE_LINE, transcript="")

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _opening)
    async with voice_room_client(
        db_session, monkeypatch, elevenlabs=elevenlabs, bucket=bucket
    ) as c:
        yield c


@pytest.fixture()
async def panorama(db_session: AsyncSession) -> IRSession:
    return await create_session(db_session, language="pt", pericope="OV")


async def _written(test_engine: Any, session_id: str) -> list[str]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as fresh:
        loaded = await fresh.get(IRSession, session_id)
        assert loaded is not None
        return [m.get("text", "") for m in loaded.messages or [] if m.get("role") == "guide"]


async def test_a_turn_answers_while_its_voice_is_still_being_made(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    test_engine: Any,
) -> None:
    elevenlabs.held.clear()
    try:
        answered = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
        )
    finally:
        elevenlabs.held.set()

    assert answered.status_code == 200
    assert answered.json()["audio_url"]
    assert await _written(test_engine, panorama.id) == [GUIDE_LINE], (
        "a resposta esperava a ElevenLabs e o upload antes de escrever o turno"
    )


async def test_the_voice_route_joins_the_line_being_voiced_instead_of_voicing_it_again(
    client: httpx.AsyncClient, panorama: IRSession, elevenlabs: Elevenlabs
) -> None:
    elevenlabs.held.clear()
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")
    listening = asyncio.create_task(client.get(answered.json()["audio_url"]))
    await asyncio.sleep(0.05)
    elevenlabs.held.set()
    heard = await asyncio.wait_for(listening, timeout=1)

    assert heard.status_code == 200
    assert heard.content == b"the rendering"
    assert elevenlabs.texts == [GUIDE_LINE], (
        "o GET não achava a síntese em voo e pagava a ElevenLabs uma segunda vez pela mesma fala"
    )


async def test_an_instance_that_holds_nothing_voices_the_line_from_the_words_in_the_session(
    client: httpx.AsyncClient, panorama: IRSession, elevenlabs: Elevenlabs
) -> None:
    elevenlabs.failures = 1
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")
    await asyncio.sleep(0.05)
    another_instance()

    heard = await client.get(answered.json()["audio_url"])

    assert heard.status_code == 200, (
        "outra instância não tinha a task nem a memória, o bucket não tinha o clipe, e a "
        "fala já escrita na sessão respondia 404 em vez de ser feita"
    )
    assert heard.content == b"the rendering"
    assert elevenlabs.texts == [GUIDE_LINE, GUIDE_LINE]


async def test_a_line_another_session_said_is_never_voiced_through_this_one(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    db_session: AsyncSession,
) -> None:
    elevenlabs.failures = 1
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")
    handle = answered.json()["audio_url"].rsplit("/", 1)[-1]
    elsewhere = await create_session(db_session, language="pt", pericope="OV")
    await append_exchange(
        db_session, elsewhere, team_utterance="", guide_response="Outra fala, de outra sessão."
    )
    await asyncio.sleep(0.05)
    another_instance()

    heard = await client.get(f"{PREFIX}/voice/{elsewhere.id}/{handle}")

    assert heard.status_code == 404
    assert elevenlabs.texts == [GUIDE_LINE], (
        "a rota sintetizava qualquer chave pedida sob uma sessão, sem que a fala fosse dela"
    )


async def test_a_line_whose_voice_failed_after_the_answer_is_voiced_again_when_asked_for(
    client: httpx.AsyncClient, panorama: IRSession, elevenlabs: Elevenlabs
) -> None:
    elevenlabs.held.clear()
    elevenlabs.failures = 1
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")
    listening = asyncio.create_task(client.get(answered.json()["audio_url"]))
    await asyncio.sleep(0.05)
    elevenlabs.held.set()
    heard = await asyncio.wait_for(listening, timeout=1)

    assert heard.status_code == 200, (
        "a síntese que falhou depois da resposta deixava o tablet sem a fala que o turno já tinha"
    )
    assert heard.content == b"the rendering"
    assert elevenlabs.texts == [GUIDE_LINE, GUIDE_LINE]


async def test_a_line_that_cannot_be_voiced_twice_is_an_outage_for_the_tablet_not_a_bad_clip(
    client: httpx.AsyncClient, panorama: IRSession, elevenlabs: Elevenlabs, test_engine: Any
) -> None:
    elevenlabs.failures = 2
    elevenlabs.failure_status = 401
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")
    await asyncio.sleep(0.05)

    heard = await client.get(answered.json()["audio_url"])

    assert answered.status_code == 200
    assert heard.status_code == 502, (
        "uma recusa da ElevenLabs no GET virava 400, e o app a tratava como clipe ruim, "
        "não como a queda que é"
    )
    assert await _written(test_engine, panorama.id) == [GUIDE_LINE]


async def test_two_instances_voicing_one_line_at_once_serve_the_same_bytes(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    bucket: WriteOnceBucket,
) -> None:
    from app.core.config import get_settings

    elevenlabs.renderings = [b"first instance", b"second instance"]
    elevenlabs.held.clear()
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")
    audio_url = answered.json()["audio_url"]
    key = from_handle(audio_url.rsplit("/", 1)[-1], settings=get_settings())
    first_instance = clip_flight.in_flight(key)
    assert first_instance is not None
    another_instance()
    listening = asyncio.create_task(client.get(audio_url))
    await asyncio.sleep(0.05)
    elevenlabs.held.set()
    heard = await asyncio.wait_for(listening, timeout=1)

    assert heard.status_code == 200
    assert elevenlabs.texts == [GUIDE_LINE, GUIDE_LINE]
    assert heard.content == await first_instance == bucket.objects[key], (
        "duas instâncias que faziam a mesma fala ao mesmo tempo serviam duas renderizações"
    )


async def test_a_movement_of_the_opening_is_voiced_again_from_the_words_the_session_kept(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    async def _opening(**_: Any) -> TurnOutcome:
        return TurnOutcome(
            speech="O todo da passagem.\n\nA cena e o convite.",
            transcript="",
            movements=["O todo da passagem.", "A cena e o convite."],
        )

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _opening)
    elevenlabs.failures = 3
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")
    await asyncio.sleep(0.05)
    another_instance()

    scene = next(s for s in answered.json()["segments"] if s["role"] == "scene")
    heard = await client.get(scene["audio_url"])

    assert heard.status_code == 200, (
        "os movimentos da abertura não ficavam em lugar nenhum, e um que falhou não tinha "
        "de onde ser refeito"
    )
    assert elevenlabs.texts[-1] == "A cena e o convite."


async def test_the_voice_route_says_how_long_it_waited_on_the_line_being_voiced(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    caplog: pytest.LogCaptureFixture,
) -> None:
    elevenlabs.held.clear()
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")
    with caplog.at_level(logging.INFO):
        listening = asyncio.create_task(client.get(answered.json()["audio_url"]))
        await asyncio.sleep(0.1)
        elevenlabs.held.set()
        await asyncio.wait_for(listening, timeout=1)

    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[voice-get]")]
    assert len(lines) == 1
    waited = re.search(r" flight=(\d+)ms", lines[0])
    assert waited is not None, "a espera pela síntese em voo não aparecia em lugar nenhum"
    assert int(waited.group(1)) >= 90


async def test_the_turns_clip_answers_a_range_like_every_other_clip(
    client: httpx.AsyncClient, panorama: IRSession
) -> None:
    answered = await client.post(f"{PREFIX}/sessions/{panorama.id}/turns")

    heard = await client.get(answered.json()["audio_url"], headers={"Range": "bytes=4-12"})

    assert heard.status_code == 206, "a fala do turno ignorava o Range que o tablet mandou"
    assert heard.content == b"rendering"
