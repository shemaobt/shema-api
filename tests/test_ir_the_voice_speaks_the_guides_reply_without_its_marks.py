"""ENG-1329 — what the team hears is the Guide's reply in its speakable form; what is kept is not.

Every case goes through the room's own turn door with the real synthesis path: ElevenLabs is
the fake and records the exact text it was asked to say, so the expectation is what the team
hears, and the stored message is read back from the session to prove the Guide's own words
were never rewritten.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.api.internalization_room import voice as voice_api
from app.core.config import get_settings
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session, get_session
from app.services.platform import tts
from tests.release_harness import PREFIX, P, a_claimed_device, team_headers
from tests.room_harness import room_client
from tests.turn_harness import the_room_agent_is


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
    def __init__(self) -> None:
        self.said: list[str] = []

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        self.said.append(json["text"])
        return SimpleNamespace(status_code=200, content=b"som", text="")


class _Guide:
    def __init__(self) -> None:
        self.reply = ""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.reply


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
    bucket = _Bucket()
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belém")

    async def settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "heard_speech", heard)
    monkeypatch.setattr(sessions_api, "settle_coverage", settled)
    per_request = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def _the_team_hears(
    client,
    db_session: AsyncSession,
    guide: _Guide,
    elevenlabs: _Elevenlabs,
    reply: str,
) -> tuple[list[str], str]:
    guide.reply = reply
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    session_id = session.id

    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=team_headers(credential),
        data={"turn_id": "turno-1"},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )

    assert answered.status_code == 200, answered.text[:300]
    db_session.expire_all()
    stored = (await get_session(db_session, session_id)).messages[-1]["text"]
    return elevenlabs.said, stored


async def test_bold_marks_and_a_bulleted_list_are_never_read_aloud_and_stay_in_the_record(
    client, db_session: AsyncSession, guide: _Guide, elevenlabs: _Elevenlabs
) -> None:
    reply = (
        "**Noemi** voltou a Belém:\n\n- Rute ficou com ela\n- Orfa voltou para casa\n\n"
        "O que vocês acham?"
    )

    said, stored = await _the_team_hears(client, db_session, guide, elevenlabs, reply)

    assert said == [
        "Noemi voltou a Belém: Rute ficou com ela. Orfa voltou para casa. O que vocês acham?"
    ], "a voz leu os asteriscos e os marcadores da lista, que a equipe só podia ouvir como ruído"
    assert stored == reply, "o turno guardado perdeu as marcas que o Guia escreveu"


async def test_a_question_folded_into_a_statement_is_voiced_as_its_own_sentence_and_stored_whole(
    client, db_session: AsyncSession, guide: _Guide, elevenlabs: _Elevenlabs
) -> None:
    reply = "Noemi voltou para Belém — o que vocês acham que ela sentiu?"

    said, stored = await _the_team_hears(client, db_session, guide, elevenlabs, reply)

    assert said == ["Noemi voltou para Belém. O que vocês acham que ela sentiu?"], (
        "a pergunta dobrada no fim da frase era lida com a entonação de afirmação"
    )
    assert stored == reply, "o turno guardado foi cortado como a fala"


async def test_a_verse_range_is_never_cut_where_its_colon_and_dash_fall(
    client, db_session: AsyncSession, guide: _Guide, elevenlabs: _Elevenlabs
) -> None:
    reply = "Vocês lembram do trecho de Rute 1:6\u201314 que acabamos de ler?"

    said, _ = await _the_team_hears(client, db_session, guide, elevenlabs, reply)

    assert said == [reply], "a referência de versículos era cortada no dois-pontos ou no travessão"


async def test_a_dash_inside_a_quoted_phrase_is_never_cut(
    client, db_session: AsyncSession, guide: _Guide, elevenlabs: _Elevenlabs
) -> None:
    reply = 'Noemi disse "fica aqui — vai ali" a Rute, e o que ela fez?'

    said, _ = await _the_team_hears(client, db_session, guide, elevenlabs, reply)

    assert said == [reply], "a frase citada era cortada no travessão de dentro das aspas"
