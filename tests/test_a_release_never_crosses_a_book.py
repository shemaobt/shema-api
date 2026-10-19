"""ENG-1248 — a release of one book's passage never marks another book's.

Passage ids are already book-qualified (E01, J01, P01), so a release names its passage
whole and no book column is needed. The release is minted through the team's own door.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import passages as route
from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.earlier_passages import earlier_passages
from tests.release_harness import (
    PREFIX,
    a_claimed_device,
    ready_session,
    team_headers,
    team_release,
)
from tests.room_harness import room_client, the_bucket_is_in_memory


async def _instantly_voiced(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
    return SimpleNamespace(key=f"tts/v/{abs(hash(text))}.mp3"), False


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(
    db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", _instantly_voiced)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as served:
        yield served


async def _marks(client: httpx.AsyncClient, tablet: str, book: str) -> dict[str, bool]:
    answered = await client.get(
        f"{PREFIX}/books/{book}/passages?language=pt", headers=team_headers(tablet)
    )
    assert answered.status_code == 200, answered.text[:300]
    return {entry["pericope"]: entry["approved"] for entry in answered.json()["passages"]}


async def test_a_jonah_release_never_marks_ruth_or_esther(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, pericope="J01", project_id=team.id)
    released = await client.post(team_release(session.id), headers=team_headers(tablet))
    assert released.status_code == 200, released.text[:300]
    assert released.json()["blockers"] == []

    jonah = await _marks(client, tablet, "Jonah")
    ruth = await _marks(client, tablet, "Ruth")
    esther = await _marks(client, tablet, "Esther")
    statuses = await earlier_passages(db_session, project_id=team.id, pericope="J02")

    assert [pericope for pericope, mark in jonah.items() if mark] == ["J01"]
    assert [pericope for pericope, mark in ruth.items() if mark] == []
    assert [pericope for pericope, mark in esther.items() if mark] == []
    assert statuses is not None
    assert {passage: status for passage, status in statuses.items() if passage != "at"} == {
        "J01": "approved"
    }
