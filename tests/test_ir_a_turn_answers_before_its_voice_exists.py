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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
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
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )

    heard = await client.get(answered.json()["audio_url"], headers={"Range": "bytes=4-12"})

    assert heard.status_code == 206, "a fala do turno ignorava o Range que o tablet mandou"
    assert heard.content == b"rendering"


async def test_a_resume_on_another_instance_never_splices_a_second_rendering_into_the_first(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    bucket: WriteOnceBucket,
) -> None:
    elevenlabs.renderings = [b"first instance rendering", b"second instance rendering"]
    bucket.refusals = 1
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
    await asyncio.sleep(0.05)
    first = await client.get(answered.json()["audio_url"])
    another_instance()

    resumed = await client.get(
        answered.json()["audio_url"],
        headers={"Range": "bytes=6-", "If-Range": first.headers["ETag"]},
    )

    assert first.status_code == 200
    if resumed.status_code == 206:
        assert resumed.content == first.content[6:], (
            "a retomada em outra instância emendava o fim de outra renderização no começo "
            "da que o tablet já tocava"
        )
    else:
        assert resumed.status_code == 200


async def test_a_clip_the_bucket_never_confirmed_is_not_served_from_memory(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    bucket: WriteOnceBucket,
) -> None:
    from app.core.config import get_settings

    elevenlabs.held.clear()
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
    audio_url = answered.json()["audio_url"]
    key = from_handle(audio_url.rsplit("/", 1)[-1], settings=get_settings())
    bucket.objects[key] = b"stored by another instance"
    bucket.refusals = 1
    elevenlabs.held.set()
    await asyncio.sleep(0.05)

    heard = await client.get(audio_url)

    assert heard.status_code == 200
    assert heard.content == b"stored by another instance", (
        "a put que falhou sem confirmar o que ficou no bucket deixava a instância servindo "
        "da memória uma renderização que o bucket nunca aceitou"
    )


async def test_a_bucket_that_refuses_every_write_is_an_outage_not_a_clip_nobody_kept(
    client: httpx.AsyncClient, panorama: IRSession, bucket: WriteOnceBucket
) -> None:
    bucket.refusals = 2
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
    await asyncio.sleep(0.05)

    heard = await client.get(answered.json()["audio_url"])

    assert heard.status_code == 502, (
        "com o bucket recusando a escrita, a instância servia uma renderização que nenhuma "
        "outra instância acharia"
    )


async def test_a_bucket_that_fails_one_read_is_a_missing_clip_not_a_broken_route(
    client: httpx.AsyncClient, panorama: IRSession, bucket: WriteOnceBucket
) -> None:
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
    await asyncio.sleep(0.05)
    another_instance()
    bucket.unreadable = 1

    heard = await client.get(answered.json()["audio_url"])

    assert heard.status_code == 200, "uma leitura do GCS que falhava virava 500 na fala do turno"
    assert heard.content == b"the rendering"


TEAM_FIRST = "Noemi voltou para Belém"


def _the_team_speaks_before_the_opening_lands(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession, panorama: IRSession
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    async def _opening(**_: Any) -> TurnOutcome:
        await append_exchange(
            db_session, panorama, team_utterance=TEAM_FIRST, guide_response="Outra fala."
        )
        return TurnOutcome(speech=GUIDE_LINE, transcript="")

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _opening)


async def test_an_opening_the_record_dropped_is_answered_only_once_its_voice_is_kept(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _the_team_speaks_before_the_opening_lands(monkeypatch, db_session, panorama)
    elevenlabs.delay = 0.2
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
    another_instance()

    heard = await client.get(answered.json()["audio_url"])

    assert heard.status_code == 200, (
        "a abertura descartada do registro respondia antes da voz existir, e nenhuma outra "
        "instância tinha de onde fazê-la"
    )
    assert heard.content == b"the rendering"


async def test_an_opening_the_record_dropped_whose_voice_fails_is_an_outage_at_once(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _the_team_speaks_before_the_opening_lands(monkeypatch, db_session, panorama)
    elevenlabs.failures = 1

    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )

    assert answered.status_code == 502, (
        "a abertura que ninguém pode refazer respondia com um endereço que só daria 404"
    )


async def test_a_team_walking_back_in_waits_on_the_line_being_voiced_instead_of_buying_it_again(
    client: httpx.AsyncClient, panorama: IRSession, elevenlabs: Elevenlabs
) -> None:
    elevenlabs.held.clear()
    await asyncio.wait_for(client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1)
    walking_back = asyncio.create_task(client.post(f"{PREFIX}/sessions/{panorama.id}/turns"))
    await asyncio.sleep(0.05)
    elevenlabs.held.set()
    again = await asyncio.wait_for(walking_back, timeout=1)
    heard = await client.get(again.json()["audio_url"])

    assert heard.content == b"the rendering"
    assert elevenlabs.texts == [GUIDE_LINE], (
        "o diga de novo, pedido enquanto a fala ainda era feita, pagava a ElevenLabs de novo"
    )


async def test_a_fixed_line_hands_out_no_address_and_voices_nothing(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    async def _fail_safe(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech="Vamos tentar de novo.", transcript="", fixed_line="A1")

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _fail_safe)

    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
    await asyncio.sleep(0.05)

    assert answered.status_code == 200
    assert answered.json()["fixed_line"] == "A1"
    assert answered.json()["audio_url"] == ""
    assert answered.json()["segments"] == []
    assert elevenlabs.texts == [], "a fala fixa, que o app já tem em áudio, era sintetizada"


async def test_a_return_while_the_bucket_refuses_every_write_never_leaves_two_renderings(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    bucket: WriteOnceBucket,
) -> None:
    elevenlabs.renderings = [b"turn", b"return", b"first get", b"second get"]
    bucket.refusals = 2
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
    await asyncio.sleep(0.05)
    again = await asyncio.wait_for(client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1)
    here = await client.get(answered.json()["audio_url"])
    another_instance()
    there = await client.get(answered.json()["audio_url"])

    assert again.status_code == 502, (
        "o diga de novo respondia com um endereço cuja fala o bucket nunca guardou"
    )
    assert here.content == there.content, "duas instâncias serviam duas renderizações da mesma fala"


async def test_an_opening_the_record_dropped_never_waits_on_its_voice_past_the_turns_bound(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    _the_team_speaks_before_the_opening_lands(monkeypatch, db_session, panorama)
    monkeypatch.setattr(get_settings(), "internalization_room_turn_bound_ms", 200)
    elevenlabs.held.clear()
    try:
        answered = await asyncio.wait_for(
            client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
        )
    finally:
        elevenlabs.held.set()

    assert answered.status_code == 502, (
        "a abertura descartada esperava a voz sem prazo, além do limite que o turno carrega"
    )


async def test_a_bucket_that_fails_the_read_behind_a_handle_is_an_outage_not_a_crash(
    client: httpx.AsyncClient, panorama: IRSession, bucket: WriteOnceBucket
) -> None:
    await asyncio.wait_for(client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1)
    again = await asyncio.wait_for(client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1)
    another_instance()
    bucket.unreadable = 1

    heard = await client.get(again.json()["audio_url"])

    assert heard.status_code == 502, "uma leitura do GCS que falhava na rota do handle virava 500"


async def test_a_bucket_read_that_fails_inside_the_one_re_voicing_still_serves_the_kept_clip(
    client: httpx.AsyncClient,
    panorama: IRSession,
    elevenlabs: Elevenlabs,
    bucket: WriteOnceBucket,
) -> None:
    elevenlabs.renderings = [b"kept", b"made again"]
    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{panorama.id}/turns"), timeout=1
    )
    await asyncio.sleep(0.05)
    another_instance()
    bucket.unreadable = 2

    heard = await client.get(answered.json()["audio_url"])

    assert heard.status_code == 200, (
        "uma leitura do bucket que falhava dentro da re-síntese gastava a única tentativa do GET"
    )
    assert heard.content == b"kept"
