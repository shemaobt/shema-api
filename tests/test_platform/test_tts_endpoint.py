from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from app.api.platform.tts import TTS_RATE_LIMIT_PER_MINUTE
from tests.baker import make_user
from tests.test_platform.conftest import auth_header

MP3 = b"\xff\xfb\x90fake-mpeg-frame"
QUESTION = "Onde essa história acontece?"


@dataclass(frozen=True)
class _Speech:
    audio: bytes = MP3
    mime_type: str = "audio/mpeg"
    etag: str = "abc123"
    cached: bool = False


def _synth(**over: object) -> AsyncMock:
    return AsyncMock(return_value=_Speech(**over))  # type: ignore[arg-type]


async def test_returns_raw_audio_mpeg_for_an_authenticated_user(db_session, client) -> None:
    # Raw bytes, NOT base64-in-JSON: a JSON envelope would force a new DTO into the SPA's
    # FROZEN contracts/ layer, and inflates a ~100 KB body by 33%.
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)

    with patch("app.api.platform.tts.synthesize_speech", _synth()):
        res = await client.post(
            "/api/platform/tts/speak",
            json={"text": QUESTION, "language": "pt-BR"},
            headers=headers,
        )

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("audio/mpeg")
    assert res.content == MP3
    assert res.headers["etag"] == "abc123"


async def test_any_authenticated_user_gets_in_without_an_app_key(db_session, client) -> None:
    # The platform belongs to no app: the user has NO role in any app (no make_user_app_role)
    # and is still served — that is the /api/uploads precedent.
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)

    with patch("app.api.platform.tts.synthesize_speech", _synth()):
        res = await client.post(
            "/api/platform/tts/speak",
            json={"text": QUESTION, "language": "en-US"},
            headers=headers,
        )

    assert res.status_code == 200


async def test_signals_when_the_clip_came_from_the_cache(db_session, client) -> None:
    # Cache warming needs to know whether it hit ElevenLabs or the bucket.
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)

    with patch("app.api.platform.tts.synthesize_speech", _synth(cached=True)):
        res = await client.post(
            "/api/platform/tts/speak",
            json={"text": QUESTION, "language": "pt-BR"},
            headers=headers,
        )

    assert res.headers["x-tts-cached"] == "1"


async def test_abuse_is_blocked_before_it_pays_elevenlabs(db_session, client) -> None:
    # This route bills per character: since the key is content-addressed, random text is a
    # guaranteed miss, and a retry loop in the SPA is a paid call on every lap.
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)
    synth = _synth()

    with patch("app.api.platform.tts.synthesize_speech", synth):
        for i in range(TTS_RATE_LIMIT_PER_MINUTE):
            ok = await client.post(
                "/api/platform/tts/speak",
                json={"text": f"{QUESTION} {i}", "language": "pt-BR"},
                headers=headers,
            )
            assert ok.status_code == 200

        blocked = await client.post(
            "/api/platform/tts/speak",
            json={"text": "one more", "language": "pt-BR"},
            headers=headers,
        )

    assert blocked.status_code == 429
    assert synth.await_count == TTS_RATE_LIMIT_PER_MINUTE  # the blocked call synthesized nothing


async def test_the_limit_is_per_user_not_per_ip(db_session, client) -> None:
    # get_remote_address would put a whole office — and all traffic behind one proxy — in a
    # single bucket: one abusive user would take everyone else's voice down.
    abuser = await make_user(db_session, email="abuser@example.com")
    innocent = await make_user(db_session, email="innocent@example.com")
    abuser_headers = await auth_header(db_session, abuser)
    innocent_headers = await auth_header(db_session, innocent)

    with patch("app.api.platform.tts.synthesize_speech", _synth()):
        for i in range(TTS_RATE_LIMIT_PER_MINUTE + 1):
            await client.post(
                "/api/platform/tts/speak",
                json={"text": f"abuse {i}", "language": "pt-BR"},
                headers=abuser_headers,
            )

        res = await client.post(
            "/api/platform/tts/speak",
            json={"text": QUESTION, "language": "pt-BR"},
            headers=innocent_headers,
        )

    assert res.status_code == 200


async def test_anonymous_is_blocked(client) -> None:
    res = await client.post("/api/platform/tts/speak", json={"text": QUESTION, "language": "pt-BR"})

    assert res.status_code in (401, 403)


async def test_empty_text_is_422(db_session, client) -> None:
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)

    res = await client.post(
        "/api/platform/tts/speak", json={"text": "", "language": "pt-BR"}, headers=headers
    )

    assert res.status_code == 422


async def test_text_that_is_too_long_is_422(db_session, client) -> None:
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)

    res = await client.post(
        "/api/platform/tts/speak",
        json={"text": "a" * 3001, "language": "pt-BR"},
        headers=headers,
    )

    assert res.status_code == 422
