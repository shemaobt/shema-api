"""A clip the room stored under a voice it no longer has is voiced again, never a 404.

Every reply the team hears is in Mariana's voice, and a stored clip the team replays is a
reply. The voice route serves only the voices the room has, so a clip kept on a row from
before the voice changed would answer 404, and sessions do not end, so that is not a window
that closes on its own.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.core.config import get_settings
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.voice_handles import from_handle
from app.services.platform import tts
from tests.release_harness import KEY, PREFIX, P
from tests.room_harness import (
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
)
from tests.turn_harness import the_room_agent_is

MARIANA = "tZ2oxQJXfOrGrN7iKnta"
RETIRED_VOICE_ID = "83Nae6GFQiNslSbuzmE7"


class Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


class ElevenLabs:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def get(self, *_: Any, **__: Any) -> SimpleNamespace:
        return SimpleNamespace(status_code=200, content=b"", text="")

    async def post(self, url: str, **_: Any) -> SimpleNamespace:
        self.spoken.append(url.rsplit("/", 1)[-1])
        return SimpleNamespace(status_code=200, content=b"audio", text="")


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch) -> Bucket:
    store = Bucket()
    monkeypatch.setattr(tts, "_default_store", lambda _: store)
    return store


@pytest.fixture()
def elevenlabs(monkeypatch: pytest.MonkeyPatch) -> ElevenLabs:
    voice = ElevenLabs()
    monkeypatch.setattr(tts, "_make_client", lambda: voice)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    return voice


async def _speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
    if "corrected_response" in system_prompt:
        return '{"verdict": "pass", "issues": []}'
    return "Vocês contaram bem."


def _served_key(audio_url: str) -> str | None:
    return from_handle(audio_url.rsplit("/", 1)[-1], settings=get_settings())


async def test_a_verdict_voiced_before_the_voice_changed_is_heard_again_in_marianas(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    bucket: Bucket,
    elevenlabs: ElevenLabs,
) -> None:
    nothing_is_read_ahead(monkeypatch)
    the_analyst_reads(monkeypatch)
    the_room_agent_is(monkeypatch, turn=_speaker)
    session, _ = await rehearsed_in_parts(db_session, 1)
    async with room_client(db_session, monkeypatch) as client:
        report = await heard_every_part(db_session, session.id)
        with monkeypatch.context() as before_the_deploy:
            before_the_deploy.setattr(
                get_settings(), "internalization_room_voice_id", RETIRED_VOICE_ID
            )
            first = await press_terminei(client, session.id, report=report)
        assert first.status_code == 200, first.text[:300]
        assert elevenlabs.spoken == [RETIRED_VOICE_ID]

        again = await press_terminei(client, session.id, report=report)

    assert again.status_code == 200, again.text[:300]
    served = _served_key(again.json()["audio_url"])
    assert served is not None, "the tablet was handed an address the voice route answers 404"
    assert served.startswith(f"tts/{MARIANA}/")
    assert served in bucket.objects


async def test_an_opening_prepared_before_the_voice_changed_is_heard_in_marianas(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    bucket: Bucket,
    elevenlabs: ElevenLabs,
) -> None:
    async def _noop_settle(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)
    session = await create_session(db_session, language="pt", pericope=P)
    session.prepared_speech = "Vamos conhecer a cena."
    session.prepared_audio_key = (
        f"tts/{RETIRED_VOICE_ID}/eleven_turbo_v2_5/mp3_44100_128/abc/def.mp3"
    )
    session.prepared_pericope = P
    await db_session.commit()

    async with room_client(db_session, monkeypatch) as client:
        opened = await client.post(
            f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY}
        )

    assert opened.status_code == 200, opened.text[:300]
    served = _served_key(opened.json()["audio_url"])
    assert served is not None, "the tablet was handed an address the voice route answers 404"
    assert served.startswith(f"tts/{MARIANA}/")
    assert served in bucket.objects
