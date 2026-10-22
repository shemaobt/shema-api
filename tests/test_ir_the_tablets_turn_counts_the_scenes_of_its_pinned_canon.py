"""ENG-1323 — the tablet's turn tells the voice the **Scene rehearsals** of the session's pinned
canon, not of the canon deployed since.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.llm import CACHE_BREAK
from tests.canon_harness import the_canon_moves_on
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.scene_rehearsal_harness import the_kept_p02_tells_its_appeals_as_one_scene
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted

NEW_PIN = "a" * 40
PINNED_P02 = (
    "SCENE REHEARSALS: parts whose recorded and translated scene rehearsal has reached you: "
    "none. Parts with none: S1, S2."
)


@pytest.fixture()
def guide_systems(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    read: list[str] = []

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="A Noemi ficou.")

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        read.append(system_prompt)
        return "Isso. Contem mais."

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return read


@pytest.fixture()
async def client(db_session: AsyncSession, guide_systems, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def test_the_tablets_turn_names_the_scenes_of_the_sessions_pinned_canon_not_the_deployed_one(
    client, db_session: AsyncSession, guide_systems: list[str], monkeypatch, tmp_path: Path
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P02"},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["session_id"]
    the_canon_moves_on(
        monkeypatch, tmp_path, NEW_PIN, keeping=the_kept_p02_tells_its_appeals_as_one_scene
    )

    await the_room_opens(client, tablet, session_id)
    await the_team_says(client, tablet, session_id, "turno-1")

    facts = guide_systems[-1].partition(CACHE_BREAK)[2]
    assert PINNED_P02 in facts, (
        "o turno do tablet contava as cenas do cânone servido, não do cânone fixado da sessão"
    )
    assert "S3" not in facts.partition("SCENE REHEARSALS:")[2].partition("\n")[0]
