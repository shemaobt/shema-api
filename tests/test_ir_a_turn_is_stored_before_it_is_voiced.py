"""ENG-1324 — a turn is stored before any sound is made, and its sound is made from that store.

Her turn route saves the exchange and the reply text before it answers, and her audio route
voices the stored text when the tablet asks for it. Ours voiced first and wrote afterwards, so
a speech engine that failed while voicing lost the whole turn: the Desk never saw it, a resend
ran the Guide again, and «Ouvir de novo» played the line before it.

Every case goes through the room's own doors with the real synthesis path: ElevenLabs is the
fake, the bucket is in memory, and the address a turn hands out is the real content key.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import append_exchange, create_session
from app.services.internalization_room.synthesize_facilitator_speech import facilitator_speech_key
from app.services.platform import tts
from tests.baker import make_app, make_role
from tests.release_harness import APP_KEY, PREFIX, P, a_claimed_device, at_the_desk, team_headers
from tests.room_harness import room_client
from tests.turn_harness import the_room_agent_is

FIRST_QUESTION = "Quem aparece nesta parte?"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"


class _Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> bytes:
        self.objects[key] = data
        return data


class _Elevenlabs:
    """The speech engine, down on command; every text it was asked for is recorded."""

    def __init__(self) -> None:
        self.down = False
        self.calls: list[str] = []

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        self.calls.append(json["text"])
        if self.down:
            return SimpleNamespace(status_code=503, content=b"", text="busy")
        return SimpleNamespace(status_code=200, content=f"som de {json['text']}".encode(), text="")


class _Guide:
    def __init__(self) -> None:
        self.drafts = 0

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.drafts += 1
        return GUIDE_LINE


@pytest.fixture()
def elevenlabs() -> _Elevenlabs:
    return _Elevenlabs()


@pytest.fixture()
def guide(monkeypatch: pytest.MonkeyPatch) -> _Guide:
    drafting = _Guide()
    the_room_agent_is(monkeypatch, turn=drafting)
    return drafting


@pytest.fixture()
async def client(
    db_session: AsyncSession,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: _Elevenlabs,
    guide: _Guide,
):
    from app.api.internalization_room import sessions as sessions_api
    from app.api.internalization_room import voice as voice_api
    from app.core.config import get_settings

    bucket = _Bucket()
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=TEAM_ANSWER)

    async def settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "heard_speech", heard)
    monkeypatch.setattr(sessions_api, "settle_coverage", settled)
    per_request = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room(db_session: AsyncSession) -> tuple[str, str, dict[str, str]]:
    """A session that has asked its question, the tablet that holds it, and the Desk."""
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    await append_exchange(db_session, session, team_utterance="", guide_response=FIRST_QUESTION)
    desk, _facilitator = await at_the_desk(db_session, app, project)
    return session.id, credential, desk


async def _the_team_answers(
    client: httpx.AsyncClient, credential: str, session_id: str, turn_id: str = "turno-1"
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=team_headers(credential),
        data={"turn_id": turn_id},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def test_a_reply_whose_voice_fails_is_still_in_the_observation_room(
    client: httpx.AsyncClient, room: tuple[str, str, dict[str, str]], elevenlabs: _Elevenlabs
) -> None:
    session_id, credential, desk = room
    elevenlabs.down = True

    answered = await _the_team_answers(client, credential, session_id)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["audio_url"], "a resposta guardada saía sem endereço para a voz"
    conversation = await client.get(
        f"{PREFIX}/facilitator/sessions/{session_id}/conversation", headers=desk
    )
    assert [(t["role"], t["text"]) for t in conversation.json()["turns"]] == [
        ("guide", FIRST_QUESTION),
        ("team", TEAM_ANSWER),
        ("guide", GUIDE_LINE),
    ], "a voz falhou e o turno inteiro sumiu da sala de observação"


async def test_an_opening_whose_voice_fails_is_stored_and_never_drafted_again(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    elevenlabs: _Elevenlabs,
    guide: _Guide,
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    elevenlabs.down = True

    def ask_for_the_opening() -> Any:
        return client.post(
            f"{PREFIX}/sessions/{session.id}/turns",
            headers=team_headers(credential),
            data={"turn_id": "abertura"},
        )

    opened = await ask_for_the_opening()
    elevenlabs.down = False
    again = await ask_for_the_opening()

    assert opened.status_code == 200, opened.text[:300]
    assert again.json() == opened.json()
    assert guide.drafts == 1, "a voz falhou na abertura e o Guia redigiu outra abertura"


async def test_the_address_of_a_reply_whose_voice_failed_makes_its_sound_once_the_engine_is_back(
    client: httpx.AsyncClient, room: tuple[str, str, dict[str, str]], elevenlabs: _Elevenlabs
) -> None:
    session_id, credential, _desk = room
    elevenlabs.down = True
    answered = await _the_team_answers(client, credential, session_id)
    elevenlabs.down = False

    heard = await client.get(answered.json()["audio_url"], headers=team_headers(credential))

    assert heard.status_code == 200, heard.text[:300]
    assert heard.content == f"som de {GUIDE_LINE}".encode(), (
        "o endereço da resposta guardada nunca fazia o som que tinha falhado"
    )


async def test_an_address_for_words_the_session_never_stored_makes_no_sound(
    client: httpx.AsyncClient, room: tuple[str, str, dict[str, str]], elevenlabs: _Elevenlabs
) -> None:
    from app.services.internalization_room.voice_handles import clip_url

    session_id, credential, _desk = room
    forged = clip_url(
        facilitator_speech_key("Uma frase que a sala nunca guardou.", language="pt"),
        session_id=session_id,
    )

    heard = await client.get(forged, headers=team_headers(credential))

    assert heard.status_code == 404, heard.text[:300]
    assert elevenlabs.calls == [], "o endereço fazia soar uma fala que a sessão não guardou"


async def test_an_address_of_another_teams_session_makes_no_sound(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    room: tuple[str, str, dict[str, str]],
    elevenlabs: _Elevenlabs,
) -> None:
    session_id, credential, _desk = room
    elevenlabs.down = True
    answered = await _the_team_answers(client, credential, session_id)
    elevenlabs.down = False
    elevenlabs.calls.clear()
    _stranger_project, stranger = await a_claimed_device(db_session, email="out@example.com")

    heard = await client.get(answered.json()["audio_url"], headers=team_headers(stranger))

    assert heard.status_code == 404, heard.text[:300]
    assert elevenlabs.calls == [], "outra equipe fazia soar a resposta guardada desta sessão"


async def test_a_take_resent_after_its_voice_failed_is_answered_from_the_stored_turn(
    client: httpx.AsyncClient,
    room: tuple[str, str, dict[str, str]],
    elevenlabs: _Elevenlabs,
    guide: _Guide,
) -> None:
    session_id, credential, _desk = room
    elevenlabs.down = True
    answered = await _the_team_answers(client, credential, session_id)
    elevenlabs.down = False

    resent = await _the_team_answers(client, credential, session_id)
    looked = await client.get(
        f"{PREFIX}/sessions/{session_id}/turns/turno-1", headers=team_headers(credential)
    )

    assert guide.drafts == 1, "a voz falhou e o reenvio da gravação chamou o Guia de novo"
    assert resent.json() == answered.json()
    assert looked.status_code == 200, looked.text[:300]
    assert looked.json() == answered.json(), "a olhada não achava o turno que tinha ficado"


async def test_hearing_it_again_after_a_reload_plays_the_reply_whose_voice_failed(
    client: httpx.AsyncClient, room: tuple[str, str, dict[str, str]], elevenlabs: _Elevenlabs
) -> None:
    session_id, credential, _desk = room
    elevenlabs.down = True
    answered = await _the_team_answers(client, credential, session_id)
    elevenlabs.down = False

    again = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns", headers=team_headers(credential)
    )
    heard = await client.get(again.json()["audio_url"], headers=team_headers(credential))

    assert again.json()["audio_url"] == answered.json()["audio_url"]
    assert heard.content == f"som de {GUIDE_LINE}".encode(), (
        "«Ouvir de novo» tocava a fala de antes, não a resposta que tinha falhado"
    )


async def test_a_turn_whose_voice_works_serves_the_clip_it_voiced_without_voicing_it_again(
    client: httpx.AsyncClient, room: tuple[str, str, dict[str, str]], elevenlabs: _Elevenlabs
) -> None:
    session_id, credential, _desk = room

    answered = await _the_team_answers(client, credential, session_id)
    heard = await client.get(answered.json()["audio_url"], headers=team_headers(credential))

    assert heard.content == f"som de {GUIDE_LINE}".encode()
    assert elevenlabs.calls == [GUIDE_LINE], "o endereço do turno pagava a mesma fala duas vezes"


async def test_a_team_walking_back_in_while_the_voice_is_down_gets_the_stored_reply_not_a_502(
    client: httpx.AsyncClient, room: tuple[str, str, dict[str, str]], elevenlabs: _Elevenlabs
) -> None:
    session_id, credential, _desk = room
    elevenlabs.down = True
    answered = await _the_team_answers(client, credential, session_id)

    again = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns", headers=team_headers(credential)
    )
    assert again.status_code == 200, again.text[:300]
    elevenlabs.down = False
    heard = await client.get(again.json()["audio_url"], headers=team_headers(credential))

    assert again.json()["audio_url"] == answered.json()["audio_url"], (
        "a equipe que voltava com a voz fora recebia outro endereço para a mesma fala"
    )
    assert heard.content == f"som de {GUIDE_LINE}".encode(), (
        "a equipe que voltava com a voz fora nunca ouvia a resposta guardada"
    )
