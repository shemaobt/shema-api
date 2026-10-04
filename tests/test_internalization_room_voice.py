"""The one voice the team ever hears, and the bucket that keeps it.

The room speaks in a single configured voice, and the same sentence must never be bought
from ElevenLabs twice — not by a second worker, and not by the process that replaces this
one on the next deploy.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.services.internalization_room import synthesize_facilitator_speech
from app.services.internalization_room.passage_lines import panorama_line_for
from app.services.internalization_room.voices import voice_for
from app.services.platform import tts

ROOM_VOICE_ID = "83Nae6GFQiNslSbuzmE7"
ROOM_VOICE_ID_EN = "x52Gqgso2pdbdr7KngsJ"
ROOM_VOICE_ID_ES = "fYypSok4m8xKqKsDwS7O"
ROOM_MODEL = "eleven_turbo_v2_5"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "elevenlabs_api_key": "fake-elevenlabs",
        "gcs_platform_bucket": "tripod-platform-test",
    }
    base.update(overrides)
    return Settings(**base)


def _ok(audio: bytes = b"audio") -> SimpleNamespace:
    return SimpleNamespace(status_code=200, content=audio, text="")


def _client(*responses: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(post=AsyncMock(side_effect=list(responses) or [_ok()]))


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.asked: list[str] = []

    async def get(self, key: str) -> bytes | None:
        self.asked.append("get")
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        self.asked.append("exists")
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.asked.append("put")
        self.objects[key] = data


class RefusingStore(MemoryStore):
    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.asked.append("put")
        raise OSError("the bucket refused the write")


async def test_the_rooms_configured_voice_is_the_one_that_speaks() -> None:
    client = _client()
    store = MemoryStore()

    speech, cached = await synthesize_facilitator_speech(
        "Que bom ter vocês aqui.",
        language="pt",
        client=client,
        store=store,
        settings=_settings(),
    )

    assert store.objects[speech.key] == b"audio"
    assert cached is False
    assert ROOM_VOICE_ID in client.post.await_args.args[0]


async def test_a_legacy_es_session_is_floored_before_the_voice_is_chosen() -> None:
    """`es` left `ROOM_LANGUAGES` in shema-api#362, but a session row persisted before that
    still carries `language="es"` and still calls this with it. Marcia's ruling stands:
    Spanish is off the air until she offers it, so this must land on the floor's own voice
    and language code, never on `voice_for("es", ...)`, which still answers — it is kept on
    purpose so a legacy row does not 500 — and would otherwise speak the Portuguese or
    English fail-safe text in the Spanish voice.
    """
    client = _client()

    await synthesize_facilitator_speech(
        "Bem-vindos de volta.",
        language="es",
        client=client,
        store=MemoryStore(),
        settings=_settings(),
    )

    body = client.post.await_args.kwargs["json"]
    assert body["language_code"] == "en"
    assert ROOM_VOICE_ID_EN in client.post.await_args.args[0]
    assert ROOM_VOICE_ID_ES not in client.post.await_args.args[0]


async def test_the_language_is_stated_rather_than_guessed() -> None:
    """`eleven_multilingual_v2` reads the language off the text; turbo obeys this field."""
    client = _client()

    await synthesize_facilitator_speech(
        "Vamos contar de novo?",
        language="pt",
        client=client,
        store=MemoryStore(),
        settings=_settings(),
    )

    body = client.post.await_args.kwargs["json"]
    assert body["language_code"] == "pt"
    assert body["model_id"] == ROOM_MODEL


async def test_the_delivery_is_tuned_rather_than_left_to_the_defaults() -> None:
    client = _client()

    await synthesize_facilitator_speech(
        "Eu escuto até o fim.",
        client=client,
        store=MemoryStore(),
        settings=_settings(),
        language="pt",
    )

    tuning = client.post.await_args.kwargs["json"]["voice_settings"]
    assert tuning["speed"] == pytest.approx(0.96)
    assert tuning["stability"] == pytest.approx(0.45)


async def test_a_repeated_line_is_never_bought_twice() -> None:
    client = _client(_ok(), _ok())
    store = MemoryStore()
    settings = _settings()

    _, first = await synthesize_facilitator_speech(
        "Eu escuto até o fim.",
        client=client,
        store=store,
        settings=settings,
        language="pt",
    )
    _, second = await synthesize_facilitator_speech(
        "Eu escuto até o fim.",
        client=client,
        store=store,
        settings=settings,
        language="pt",
    )

    assert (first, second) == (False, True)
    assert client.post.await_count == 1


async def test_a_cold_process_still_finds_the_line_in_the_bucket() -> None:
    """The old in-process cache started empty on every worker and every deploy."""
    warm = MemoryStore()
    await synthesize_facilitator_speech(
        "A sala continua aqui.",
        client=_client(),
        store=warm,
        settings=_settings(),
        language="pt",
    )

    cold = MemoryStore()
    cold.objects = dict(warm.objects)
    client = _client()

    _, cached = await synthesize_facilitator_speech(
        "A sala continua aqui.",
        client=client,
        store=cold,
        settings=_settings(),
        language="pt",
    )

    assert cached is True
    assert client.post.await_count == 0


async def test_the_panoramas_own_line_is_served_from_cache_without_a_model_call() -> None:
    """The raio rides the same bucket cache as every other facilitator line — a warm cache
    answers it without ever reaching ElevenLabs."""
    line = panorama_line_for("pt")
    warm = MemoryStore()
    await synthesize_facilitator_speech(
        line,
        client=_client(),
        store=warm,
        settings=_settings(),
        language="pt",
    )

    cold = MemoryStore()
    cold.objects = dict(warm.objects)
    client = _client()

    _, cached = await synthesize_facilitator_speech(
        line,
        client=client,
        store=cold,
        settings=_settings(),
        language="pt",
    )

    assert cached is True
    assert client.post.await_count == 0


async def test_retuning_the_voice_does_not_serve_the_old_delivery() -> None:
    store = MemoryStore()
    client = _client(_ok(b"firme"), _ok(b"mais-solto"))

    await synthesize_facilitator_speech(
        "Vamos juntos.",
        client=client,
        store=store,
        settings=_settings(),
        language="pt",
    )
    speech, cached = await synthesize_facilitator_speech(
        "Vamos juntos.",
        client=client,
        store=store,
        settings=_settings(internalization_room_voice_stability=0.9),
        language="pt",
    )

    assert cached is False
    assert store.objects[speech.key] == b"mais-solto"


async def test_the_facilitators_voice_never_spells_the_divine_name_in_portuguese() -> None:
    client = _client()

    await synthesize_facilitator_speech(
        "O narrador nunca diz que foi YHWH.",
        language="pt",
        client=client,
        store=MemoryStore(),
        settings=_settings(),
    )

    spoken = client.post.await_args.kwargs["json"]["text"]
    assert "YHWH" not in spoken
    assert "Senhor Jeová" in spoken


async def test_the_facilitators_voice_never_spells_the_divine_name_in_english() -> None:
    client = _client()

    await synthesize_facilitator_speech(
        "The narrator never says it was YHWH.",
        language="en",
        client=client,
        store=MemoryStore(),
        settings=_settings(),
    )

    spoken = client.post.await_args.kwargs["json"]["text"]
    assert "YHWH" not in spoken
    assert "the LORD" in spoken


async def test_a_different_voice_id_is_honoured() -> None:
    client = _client()

    await synthesize_facilitator_speech(
        "Outra voz.",
        language="pt",
        client=client,
        store=MemoryStore(),
        settings=_settings(internalization_room_voice_id="OtherVoiceId123"),
    )

    assert "OtherVoiceId123" in client.post.await_args.args[0]


def test_voice_for_still_answers_es_directly_because_the_floor_is_the_caller_s_job() -> None:
    """Pins the boundary shema-api#362 chose: `voice_for` never refuses `es`.

    Refusing it here would 500 a session row already persisted with `language="es"`; the
    floor that keeps it off the air lives in `synthesize_facilitator_speech`, applied before
    this is ever reached. If this function ever refused `es` on its own, a legacy row would
    fail differently but still fail, and the fix belongs one layer up, not here.
    """
    assert voice_for("es", settings=_settings()) == ROOM_VOICE_ID_ES


async def _say(line: str, *, store: MemoryStore, client: SimpleNamespace) -> str:
    speech, _ = await synthesize_facilitator_speech(
        line, client=client, store=store, settings=_settings(), language="pt"
    )
    return speech.key


async def test_a_line_voiced_here_is_found_again_by_its_key_without_asking_the_bucket() -> None:
    store = MemoryStore()
    client = _client(_ok(), _ok())
    first = await _say("Vocês lembram o que Noemi disse?", store=store, client=client)
    store.asked.clear()

    again = await _say("Vocês lembram o que Noemi disse?", store=store, client=client)

    assert again == first
    assert store.asked == [], (
        "repetir a fala do Guia ou abrir a roda baixava o MP3 inteiro do bucket só para "
        "descobrir a chave que o servidor já tinha acabado de gravar"
    )
    assert client.post.await_count == 1


async def test_a_line_the_bucket_already_holds_is_neither_downloaded_nor_voiced_again() -> None:
    warm = MemoryStore()
    line = "Contem de novo a parte da colheita."
    key = await _say(line, store=warm, client=_client())
    tts.forget_what_is_kept()
    cold = MemoryStore()
    cold.objects = dict(warm.objects)
    client = _client()

    again = await _say(line, store=cold, client=client)

    assert again == key
    assert cold.asked == ["exists"], (
        "uma instância nova baixava o arquivo inteiro para saber que ele existia"
    )
    assert client.post.await_count == 0, "a mesma linha ganhava uma segunda gravação no bucket"


async def test_a_clip_the_bucket_refused_is_not_trusted_to_be_there() -> None:
    store = RefusingStore()
    client = _client(_ok(), _ok())
    await _say("Quem voltou para Belém?", store=store, client=client)
    store.asked.clear()

    await _say("Quem voltou para Belém?", store=store, client=client)

    assert store.asked[:1] == ["exists"], (
        "uma chave cujo upload falhou era lembrada como guardada, e o tablet recebia um "
        "endereço para um clipe que nenhuma outra instância achava"
    )


async def test_after_an_hour_a_known_line_is_asked_of_the_bucket_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [1000.0]
    monkeypatch.setattr(tts, "time", SimpleNamespace(monotonic=lambda: now[0]))
    store = MemoryStore()
    client = _client(_ok(), _ok())
    await _say("E depois, o que aconteceu?", store=store, client=client)
    now[0] += 3599
    store.asked.clear()
    await _say("E depois, o que aconteceu?", store=store, client=client)
    assert store.asked == []

    now[0] += 2
    await _say("E depois, o que aconteceu?", store=store, client=client)

    assert store.asked == ["exists"], (
        "uma chave lembrada para sempre continuava sendo entregue mesmo que o objeto "
        "tivesse saído do bucket"
    )
