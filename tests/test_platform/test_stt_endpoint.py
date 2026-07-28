from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.api.platform.stt import MAX_AUDIO_BYTES, STT_RATE_LIMIT_PER_MINUTE
from tests.baker import make_user
from tests.test_platform.conftest import auth_header

WEBM = b"\x1a\x45\xdf\xa3 fake webm/opus bytes"
TRANSCRIPT = "a história começa no rio"


def _upload(audio: bytes = WEBM, language: str = "pt-BR", **data: str) -> dict:
    return {
        "files": {"file": ("answer.webm", audio, "audio/webm")},
        "data": {"language": language, **data},
    }


async def test_transcribes_an_uploaded_recording(db_session, client) -> None:
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)
    stt = AsyncMock(return_value=TRANSCRIPT)

    with patch("app.api.platform.stt.transcribe_speech", stt):
        res = await client.post("/api/platform/stt/transcribe", headers=headers, **_upload())

    assert res.status_code == 200
    assert res.json() == {"text": TRANSCRIPT}
    assert stt.await_args.kwargs["language"] == "pt-BR"


async def test_the_upload_content_type_is_what_reaches_the_provider(db_session, client) -> None:
    # Scribe is told what the container is; guessing it from the bytes is the legacy
    # clients' fallback, not a first choice.
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)
    stt = AsyncMock(return_value=TRANSCRIPT)

    with patch("app.api.platform.stt.transcribe_speech", stt):
        await client.post(
            "/api/platform/stt/transcribe",
            headers=headers,
            files={"file": ("answer.ogg", WEBM, "audio/ogg")},
            data={"language": "pt-BR"},
        )

    assert stt.await_args.kwargs["mime_type"] == "audio/ogg"


async def test_an_explicit_mime_type_overrides_the_upload_one(db_session, client) -> None:
    # Same escape hatch the two existing audio endpoints give: some browsers post
    # application/octet-stream for a perfectly good WebM.
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)
    stt = AsyncMock(return_value=TRANSCRIPT)

    with patch("app.api.platform.stt.transcribe_speech", stt):
        await client.post(
            "/api/platform/stt/transcribe",
            headers=headers,
            files={"file": ("answer", WEBM, "application/octet-stream")},
            data={"language": "pt-BR", "mime_type": "audio/webm"},
        )

    assert stt.await_args.kwargs["mime_type"] == "audio/webm"


async def test_any_authenticated_user_gets_in_without_an_app_key(db_session, client) -> None:
    # The platform belongs to no app — same as the TTS route.
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)

    with patch("app.api.platform.stt.transcribe_speech", AsyncMock(return_value=TRANSCRIPT)):
        res = await client.post(
            "/api/platform/stt/transcribe", headers=headers, **_upload(language="en-US")
        )

    assert res.status_code == 200


async def test_anonymous_is_blocked(client) -> None:
    res = await client.post("/api/platform/stt/transcribe", **_upload())

    assert res.status_code in (401, 403)


async def test_an_oversize_upload_never_reaches_the_provider(db_session, client) -> None:
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)
    stt = AsyncMock(return_value=TRANSCRIPT)

    with patch("app.api.platform.stt.transcribe_speech", stt):
        res = await client.post(
            "/api/platform/stt/transcribe", headers=headers, **_upload(b"x" * (MAX_AUDIO_BYTES + 1))
        )

    assert res.status_code == 400
    assert stt.await_count == 0


async def test_a_missing_language_is_422(db_session, client) -> None:
    # The interview language is the hint that keeps Portuguese from coming back as
    # phonetic Spanish, so it is required rather than defaulted.
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)

    res = await client.post(
        "/api/platform/stt/transcribe",
        headers=headers,
        files={"file": ("answer.webm", WEBM, "audio/webm")},
    )

    assert res.status_code == 422


async def test_abuse_is_blocked_before_it_pays_elevenlabs(db_session, client) -> None:
    user = await make_user(db_session)
    headers = await auth_header(db_session, user)
    stt = AsyncMock(return_value=TRANSCRIPT)

    with patch("app.api.platform.stt.transcribe_speech", stt):
        for _ in range(STT_RATE_LIMIT_PER_MINUTE):
            ok = await client.post("/api/platform/stt/transcribe", headers=headers, **_upload())
            assert ok.status_code == 200

        blocked = await client.post("/api/platform/stt/transcribe", headers=headers, **_upload())

    assert blocked.status_code == 429
    assert stt.await_count == STT_RATE_LIMIT_PER_MINUTE  # the blocked call transcribed nothing


async def test_the_limit_is_per_user_not_per_ip(db_session, client) -> None:
    abuser = await make_user(db_session, email="abuser@example.com")
    innocent = await make_user(db_session, email="innocent@example.com")
    abuser_headers = await auth_header(db_session, abuser)
    innocent_headers = await auth_header(db_session, innocent)

    with patch("app.api.platform.stt.transcribe_speech", AsyncMock(return_value=TRANSCRIPT)):
        for _ in range(STT_RATE_LIMIT_PER_MINUTE + 1):
            await client.post("/api/platform/stt/transcribe", headers=abuser_headers, **_upload())

        res = await client.post(
            "/api/platform/stt/transcribe", headers=innocent_headers, **_upload()
        )

    assert res.status_code == 200
