"""Not hearing someone is an ordinary moment in a room, not a client error.

The transcriber raises for silence, for a clipped recording, and for a file the encoder
mangled. Left to propagate, each of those becomes a 4xx — and the app has one drawing for
every failure it cannot act on, the one that says the network is down. A team would be told
the internet failed because somebody sat too far from the microphone.
"""

import pytest

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.services.internalization_room import hearing


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db")


async def test_what_the_team_said_comes_back_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _transcribe(*_: object, **__: object) -> str:
        return "a gente contou de novo"

    monkeypatch.setattr(hearing, "transcribe_audio", _transcribe)

    assert await hearing.heard(b"audio", settings=_settings()) == "a gente contou de novo"


@pytest.mark.parametrize(
    "reason",
    [
        "Transcription returned empty text",
        "Transcription request failed with status 400",
        "Audio payload is empty",
    ],
)
async def test_silence_and_mangled_audio_answer_empty_rather_than_raise(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    async def _transcribe(*_: object, **__: object) -> str:
        raise ValidationError(reason)

    monkeypatch.setattr(hearing, "transcribe_audio", _transcribe)

    assert await hearing.heard(b"audio", settings=_settings()) == ""


async def test_an_empty_answer_is_what_the_fail_safe_line_was_written_for() -> None:
    """`run_turn` speaks INAUDIBLE on an empty transcript — a branch that was unreachable
    while the transcriber raised instead of returning nothing."""
    from app.services.internalization_room.fail_safe import FailSafe, choose

    line, name = choose(FailSafe.INAUDIBLE, "pt", turn=0)

    assert name == "D0"
    assert "ouvir" in line
