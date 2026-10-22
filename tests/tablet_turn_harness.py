"""What the cases that speak a turn through the room's own door share.

Plain builders only: the fixtures that call them stay in each module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import PREFIX, team_headers
from tests.turn_harness import the_room_agent_is


def the_turn_is_scripted(
    monkeypatch: pytest.MonkeyPatch,
    *,
    heard: Callable[..., Awaitable[HeardSpeech]],
    model: Callable[..., Awaitable[str]],
) -> None:
    """Put the recognizer and the Guide's model in the case's hands, and silence the rest.

    The voice answers a fixed clip and the coverage settle does nothing, so a turn through
    the real route needs neither a synthesiser nor a background task.
    """

    async def voice(text: str, **_: Any):
        return (
            SynthesizedSpeech(
                audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/x.mp3"
            ),
            False,
        )

    async def settled(**_: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api, "heard_speech", heard)
    the_room_agent_is(monkeypatch, turn=model)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", settled)


async def the_team_says(
    client: httpx.AsyncClient, credential: str, session_id: str, turn_id: str
) -> httpx.Response:
    response = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=team_headers(credential),
        data={"turn_id": turn_id},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )
    assert response.status_code == 200, response.text[:300]
    return response


async def the_room_opens(
    client: httpx.AsyncClient, credential: str, session_id: str
) -> httpx.Response:
    """A turn with no recording: the opening on a fresh session, the last line again after."""
    response = await client.post(
        f"{PREFIX}/sessions/{session_id}/turns", headers=team_headers(credential)
    )
    assert response.status_code == 200, response.text[:300]
    return response
