from __future__ import annotations

from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.internalization_room import fail_safe
from app.services.platform import tts
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client

THE_TABLET = {"X-Room-Key": KEY}

ACKS_AS_RULED = """
### F. Instant acknowledgements

- "Mm-hm."
- "Okay."
- "Mmm — let me think about that for a moment."
- "Right."

### F-pt. (Português brasileiro)

- "Hmm."
- "Certo."
- "Deixa eu pensar um instante."
- "Tá."
"""


class Bucket:
    def __init__(self) -> None:
        self.kept: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.kept.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.kept

    async def put(self, key: str, data: bytes, content_type: str) -> bytes:
        return self.kept.setdefault(key, data)


class ElevenLabs:
    def __init__(self) -> None:
        self.voiced: list[str] = []

    async def post(self, url: str, *, json: dict[str, Any], **_: Any) -> SimpleNamespace:
        self.voiced.append(json["text"])
        return SimpleNamespace(status_code=200, content=f"voz:{json['text']}".encode(), text="")


@pytest.fixture
def elevenlabs(monkeypatch: pytest.MonkeyPatch) -> ElevenLabs:
    from app.api.internalization_room import voice as voice_api

    voice, bucket = ElevenLabs(), Bucket()
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: voice)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)
    return voice


@pytest.fixture
def deploy(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], None]]:
    def deployed(her_file: str) -> None:
        monkeypatch.setattr(fail_safe, "fail_safe_utterances", lambda: her_file)
        fail_safe._sections.cache_clear()
        tts.forget_what_is_kept()

    yield deployed
    fail_safe._sections.cache_clear()


async def heard(client: httpx.AsyncClient, line: str, language: str) -> tuple[str, str]:
    asked = await client.get(
        f"{PREFIX}/fixed-lines/{line}", params={"language": language}, headers=THE_TABLET
    )
    assert asked.status_code == 200, asked.text
    address = asked.json()["audio_url"]
    clip = await client.get(address, headers=THE_TABLET)
    assert clip.status_code == 200, clip.text
    return address, clip.content.decode()


async def test_a_re_ruled_acknowledgement_is_heard_in_its_new_words_on_the_next_load(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
) -> None:
    deploy(ACKS_AS_RULED)
    async with room_client(db_session, monkeypatch) as client:
        _, before = await heard(client, "F2", "pt")
        deploy(ACKS_AS_RULED.replace("Deixa eu pensar um instante.", "Deixa eu pensar."))
        _, after = await heard(client, "F2", "pt")

    assert before == "voz:Deixa eu pensar um instante."
    assert after == "voz:Deixa eu pensar.", (
        "a linha ia gravada dentro do app e só mudava com uma versão nova na loja"
    )


async def test_the_old_sound_is_never_answered_again_once_the_line_is_re_ruled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
) -> None:
    deploy(ACKS_AS_RULED)
    async with room_client(db_session, monkeypatch) as client:
        old, _ = await heard(client, "F2", "pt")
        deploy(ACKS_AS_RULED.replace("Deixa eu pensar um instante.", "Deixa eu pensar."))
        first = await heard(client, "F2", "pt")
        second = await heard(client, "F2", "pt")

    assert first == second == (first[0], "voz:Deixa eu pensar."), (
        "o segundo pedido depois da mudança voltava a tocar a fala antiga"
    )
    assert old != first[0]


async def test_a_line_whose_text_did_not_change_is_not_voiced_again(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
) -> None:
    deploy(ACKS_AS_RULED)
    async with room_client(db_session, monkeypatch) as client:
        before = await heard(client, "F1", "pt")
        deploy(ACKS_AS_RULED.replace("Deixa eu pensar um instante.", "Deixa eu pensar."))
        after = await heard(client, "F1", "pt")

    assert after == before == (before[0], "voz:Certo.")
    assert elevenlabs.voiced == ["Certo."], (
        "uma fala que ninguém mudou era sintetizada de novo a cada deploy"
    )


async def test_an_english_line_re_ruled_is_heard_new_in_english_and_portuguese_keeps_its_own(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
) -> None:
    deploy(ACKS_AS_RULED)
    async with room_client(db_session, monkeypatch) as client:
        portuguese = await heard(client, "F2", "pt")
        deploy(
            ACKS_AS_RULED.replace("Mmm — let me think about that for a moment.", "Let me think.")
        )
        english = await heard(client, "F2", "en")
        still = await heard(client, "F2", "pt")

    assert english[1] == "voz:Let me think."
    assert still == portuguese == (portuguese[0], "voz:Deixa eu pensar um instante."), (
        "a mudança numa língua mexia na fala da outra"
    )
