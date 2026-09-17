"""Not hearing someone is an ordinary moment in a room, not a client error.

The transcriber raises for silence, for a clipped recording, and for a file the encoder
mangled. Left to propagate, each of those becomes a 4xx — and the app has one drawing for
every failure it cannot act on, the one that says the network is down. A team would be told
the internet failed because somebody sat too far from the microphone.
"""

from types import SimpleNamespace

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


@pytest.mark.parametrize(
    ("spoken", "detected"),
    [("pt", "pt"), ("pt", "por"), ("en", "en"), ("en", "eng")],
)
def test_a_team_speaking_the_sessions_own_language_is_never_heard_as_mother_tongue(
    spoken: str, detected: str
) -> None:
    """Numa sessão que não fosse em português, cada turno caía na linha G e o Guia nunca
    era chamado: a régua era a lista `{"pt", "por"}`, não a língua da sessão."""
    heard_it = hearing.HeardSpeech(
        text="a family leaves Bethlehem because there is no bread",
        bridge_language=spoken,
        language_code=detected,
        language_probability=0.99,
    )

    assert heard_it.mother_tongue is False
    assert heard_it.reliable_bridge_speech is True


def test_speech_outside_the_sessions_language_still_meets_the_boundary() -> None:
    heard_it = hearing.HeardSpeech(
        text="uma família sai de Belém porque não há pão",
        bridge_language="en",
        language_code="pt",
        language_probability=0.99,
    )

    assert heard_it.mother_tongue is True


async def test_the_session_names_the_language_the_hearing_is_measured_against(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _detailed(*_: object, **__: object) -> object:
        return SimpleNamespace(
            text="a family leaves Bethlehem",
            language_code="en",
            language_probability=0.99,
            transcript_confidence=0.9,
        )

    monkeypatch.setattr(hearing, "transcribe_audio_detailed", _detailed)

    in_english = await hearing.heard_speech(b"audio", language="en", settings=_settings())
    in_portuguese = await hearing.heard_speech(b"audio", language="pt", settings=_settings())

    assert in_english.mother_tongue is False
    assert in_portuguese.mother_tongue is True
