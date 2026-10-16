"""ENG-1344 — the tablet reads its session's scenes, in passage order, with their titles.

Before recording a **Scene rehearsal** on a passage of two or more scenes the tablet asks
«Qual cena vocês vão ensaiar?» with one button per **Scene**. It holds no scene of the passage,
so the room answers them: each scene's id, the label the keep stores as the team's, and its
title in the session's language. The cases read the door through the real routes against the
vendored canon.
"""

from __future__ import annotations

import io
import wave
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.sessions import create_session
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.release_harness import PREFIX
from tests.room_harness import room_client, the_bucket_is_in_memory


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def a_session(db: AsyncSession, pericope: str, language: str = "pt") -> str:
    session = await create_session(db, pericope=pericope, project_id=TABLET_TEAM, language=language)
    return str(session.id)


async def scenes_of(
    client: httpx.AsyncClient, session_id: str, headers: dict[str, str] | None = None
) -> httpx.Response:
    return await client.get(f"{PREFIX}/sessions/{session_id}/scenes", headers=headers)


async def the_scenes(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    answered = await scenes_of(client, session_id)
    assert answered.status_code == 200, answered.text
    return list(answered.json()["scenes"])


def recording(tone: int) -> bytes:
    """Two seconds of 16 kHz mono WAV whose bytes differ by `tone`."""
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(tone.to_bytes(2, "little", signed=True) * 32_000)
    return out.getvalue()


async def test_the_tablet_reads_its_sessions_scenes_in_passage_order_with_ids_and_portuguese_titles(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, "P02")

    assert await the_scenes(client, session_id) == [
        {"scene_id": "S1", "title": "Ouvir a notícia e partir"},
        {"scene_id": "S2", "title": "Primeiro apelo e recusa"},
        {"scene_id": "S3", "title": "Segundo apelo e a separação"},
    ]


async def test_an_english_session_reads_the_maps_own_titles(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, "P02", language="en")

    assert [scene["title"] for scene in await the_scenes(client, session_id)] == [
        "Hearing and setting out",
        "First appeal and refusal",
        "Second appeal and the split",
    ]


async def test_a_passage_of_one_scene_answers_its_one_scene(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, "P14")

    assert await the_scenes(client, session_id) == [
        {"scene_id": "S1", "title": "As gerações de Perez"}
    ]


async def test_a_panorama_session_answers_no_scenes(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, "OV-Ruth")

    answered = await scenes_of(client, session_id)

    assert answered.status_code == 200, answered.text
    assert answered.json() == {"scenes": []}


async def test_another_teams_tablet_cannot_read_a_sessions_scenes(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, "P02")
    stranger = await a_linked_tablet(db_session)

    refused = await scenes_of(client, session_id, headers=stranger.headers)

    assert (await scenes_of(client, session_id)).status_code == 200
    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "NOT_FOUND"


async def test_a_scene_carries_only_its_id_and_its_title(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, "P02")

    assert [set(scene) for scene in await the_scenes(client, session_id)] == [
        {"scene_id", "title"}
    ] * 3


async def test_every_scene_id_the_door_answers_is_a_label_the_keep_stores_as_the_teams(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, "P02")
    answered = [scene["scene_id"] for scene in await the_scenes(client, session_id)]

    stored = []
    for tone, scene_id in enumerate(answered, start=1):
        kept = await client.post(
            f"{PREFIX}/sessions/{session_id}/scene-rehearsals",
            data={"scene": scene_id},
            files={"file": ("cena.wav", recording(tone), "audio/wav")},
        )
        assert kept.status_code == 200, kept.text
        stored.append(kept.json()["scene"])

    assert answered and stored == answered
