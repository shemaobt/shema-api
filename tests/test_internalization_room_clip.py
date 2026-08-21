"""The line the team hears has an address, and that address never changes its bytes.

Audio used to ride inside the turn's JSON as base64 — a third more bytes than the MP3, paid
again on every replay, over the kind of connection a translation team actually has.
"""

import pytest

from app.core.config import Settings
from app.services.internalization_room.voice_handles import (
    clip_url,
    from_handle,
    to_handle,
)


def _settings(**over: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "internalization_room_voice_id": "RoomVoice",
    }
    base.update(over)
    return Settings(**base)


KEY = "tts/RoomVoice/eleven_turbo_v2_5/mp3_44100_128/abc123/def456.mp3"


def test_a_handle_survives_the_round_trip() -> None:
    assert from_handle(to_handle(KEY), settings=_settings()) == KEY


def test_the_address_is_one_path_segment() -> None:
    """The key has slashes; a handle that kept them would need a different route shape."""
    handle = clip_url(KEY).removeprefix("/api/internalization-room/voice/")
    assert "/" not in handle


def test_the_app_never_learns_the_voice_behind_the_line() -> None:
    assert "RoomVoice" not in clip_url(KEY)
    assert "eleven_turbo" not in clip_url(KEY)


@pytest.mark.parametrize(
    "key",
    [
        "tts/AnotherApp/m/f/x.mp3",
        "tts/RoomVoiceLookalike/m/f/x.mp3",
        "recordings/someone/private.m4a",
        "tts/RoomVoice/../../etc/passwd",
    ],
)
def test_a_handle_for_something_else_is_refused(key: str) -> None:
    """A handle is a client-supplied instruction about which object to read.

    The bucket holds every app's speech; nothing in it but this room's own voice is this
    route's business.
    """
    assert from_handle(to_handle(key), settings=_settings()) is None


@pytest.mark.parametrize("handle", ["", "!!!", "nao-e-base64!!", "eyJ"])
def test_a_malformed_handle_is_refused_rather_than_raised(handle: str) -> None:
    assert from_handle(handle, settings=_settings()) is None
