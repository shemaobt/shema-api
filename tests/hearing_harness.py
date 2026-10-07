"""The outside world a take meets on its way to the Guide: the recognizer and the probe.

Only those two are doubled here, at the seam `hearing` reads them through, so a case drives
the real decision of what the take was and the real turn behind it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from app.core.exceptions import NoWordsHeard, ValidationError
from app.services.internalization_room import hearing
from app.services.translation_helper.transcribe_audio import TranscriptionResult
from tests.text_seam_harness import GOLDEN


def the_transcriber_hears(
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    language_code: str | None,
    language_probability: float | None,
    *,
    transcript_confidence: float | None = None,
) -> None:
    async def detailed(*_: Any, **__: Any) -> TranscriptionResult:
        return TranscriptionResult(
            text=text,
            language_code=language_code,
            language_probability=language_probability,
            transcript_confidence=transcript_confidence,
        )

    monkeypatch.setattr(hearing, "transcribe_audio_detailed", detailed)


def the_transcriber_hears_no_words(
    monkeypatch: pytest.MonkeyPatch,
    language_code: str | None = None,
    language_probability: float | None = None,
) -> None:
    """The recognizer listened and wrote nothing, still naming the language it heard."""

    async def detailed(*_: Any, **__: Any) -> TranscriptionResult:
        raise NoWordsHeard(
            "Transcription returned empty text",
            language_code=language_code,
            language_probability=language_probability,
        )

    monkeypatch.setattr(hearing, "transcribe_audio_detailed", detailed)


def the_transcriber_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """The recognizer turned the request down (a 422), the way a misconfigured model does."""

    async def detailed(*_: Any, **__: Any) -> TranscriptionResult:
        raise ValidationError("Transcription request failed with status 422")

    monkeypatch.setattr(hearing, "transcribe_audio_detailed", detailed)


def the_take_lasts(monkeypatch: pytest.MonkeyPatch, ms: int | None) -> None:
    async def measure(_: bytes) -> int | None:
        return ms

    monkeypatch.setattr(hearing, "measure_ms", measure)


def the_probe_never_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def measure(_: bytes) -> int | None:
        await asyncio.Event().wait()
        return 25_000

    monkeypatch.setattr(hearing, "measure_ms", measure)


def the_probe_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def measure(_: bytes) -> int | None:
        raise OSError("ffprobe could not be started")

    monkeypatch.setattr(hearing, "measure_ms", measure)


def nothing_settles(monkeypatch: pytest.MonkeyPatch) -> None:
    """The coverage classifier runs after the reply; a case about the turn does not wait on it."""
    from app.api.internalization_room import sessions as sessions_api

    async def settle(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "settle_coverage", settle)


async def a_golden_session(client: httpx.AsyncClient) -> str:
    """A Portuguese P01 session opened through the Golden doors, the opening already said."""
    created = await client.post(
        f"{GOLDEN}/session", json={"pericopeId": "P01", "language": "Brazilian Portuguese"}
    )
    session_id: str = created.json()["sessionId"]
    await client.post(f"{GOLDEN}/turn", json={"sessionId": session_id, "roomNote": "session_start"})
    return session_id
