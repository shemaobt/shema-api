"""ENG-1445: the tablet's one look at a turn it gave up on, answered without running it.

Posting the same `turn_id` again re-runs the turn when a file is attached and falls into
the "say it again" line when none is, so there was no way to ask whether a turn landed
without doing it. The look is a read: 200 with what the turn door answered, 202 while the
turn is still in flight, 404 for an id nothing answered and for another team's session.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session, get_session
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import PREFIX, P, a_claimed_device, team_headers
from tests.room_harness import room_client
from tests.turn_harness import the_room_agent_is

GUIDE_LINE = "Vamos ficar nesta cena. O que voces contariam?"


class _Hearing:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *_: Any, **__: Any) -> HeardSpeech:
        self.calls += 1
        return HeardSpeech(text="Noemi voltou para Belem com Rute")


class _Model:
    """A Guide that drafts one line and a Validator that passes it; it can be held mid-answer."""

    def __init__(self) -> None:
        self.calls = 0
        self.held = asyncio.Event()
        self.thinking = asyncio.Event()
        self.held.set()

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        self.calls += 1
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.thinking.set()
        await self.held.wait()
        return GUIDE_LINE


class _Voice:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        self.calls += 1
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/turno-{self.calls}.mp3",
        )
        return entry, False


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture()
async def client(db_session, monkeypatch, per_request):
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
def fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    hearing, model, voice = _Hearing(), _Model(), _Voice()
    monkeypatch.setattr(sessions_api, "heard_speech", hearing)
    the_room_agent_is(monkeypatch, turn=model)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)
    return {"hearing": hearing, "model": model, "voice": voice}


def _calls(fakes: dict[str, Any]) -> tuple[int, int, int]:
    return fakes["hearing"].calls, fakes["model"].calls, fakes["voice"].calls


async def _post_a_turn(client, session_id: str, headers: dict[str, str], turn_id: str):
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=headers,
        data={"turn_id": turn_id},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def _look_at(client, session_id: str, headers: dict[str, str], turn_id: str):
    return await client.get(f"{PREFIX}/sessions/{session_id}/turns/{turn_id}", headers=headers)


async def test_a_turn_that_landed_is_read_back_as_the_turn_door_answered_it(
    client, db_session: AsyncSession, fakes
) -> None:
    team, credential = await a_claimed_device(db_session, email="landed@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=team.id)
    headers = team_headers(credential)

    posted = await _post_a_turn(client, session.id, headers, "turno-1")
    looked = await _look_at(client, session.id, headers, "turno-1")

    assert posted.status_code == 200, posted.text[:300]
    assert looked.status_code == 200, looked.text[:300]
    assert looked.json() == posted.json()


async def test_a_turn_still_in_flight_is_answered_as_in_flight(
    client, db_session: AsyncSession, fakes
) -> None:
    team, credential = await a_claimed_device(db_session, email="flight@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=team.id)
    headers = team_headers(credential)
    fakes["model"].held.clear()

    posting = asyncio.create_task(_post_a_turn(client, session.id, headers, "turno-1"))
    await asyncio.wait_for(fakes["model"].thinking.wait(), timeout=5)
    during = await _look_at(client, session.id, headers, "turno-1")
    fakes["model"].held.set()
    posted = await posting
    after = await _look_at(client, session.id, headers, "turno-1")

    assert during.status_code == 202, during.text[:300]
    assert during.content == b""
    assert after.status_code == 200, after.text[:300]
    assert after.json() == posted.json()


async def test_a_turn_id_nothing_answered_is_not_found(
    client, db_session: AsyncSession, fakes
) -> None:
    team, credential = await a_claimed_device(db_session, email="unknown@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=team.id)

    looked = await _look_at(client, session.id, team_headers(credential), "ninguem-respondeu")

    assert looked.status_code == 404, looked.text[:300]


async def test_another_team_cannot_read_a_teams_turn(
    client, db_session: AsyncSession, fakes
) -> None:
    owner, credential_owner = await a_claimed_device(db_session, email="owner@example.com")
    _other, credential_other = await a_claimed_device(db_session, email="other@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)
    posted = await _post_a_turn(client, session.id, team_headers(credential_owner), "turno-1")
    assert posted.status_code == 200, posted.text[:300]
    other = team_headers(credential_other)

    looked = await _look_at(client, session.id, other, "turno-1")
    session_read = await client.get(f"{PREFIX}/sessions/{session.id}", headers=other)

    assert looked.status_code == 404, looked.text[:300]
    assert looked.status_code == session_read.status_code
    assert looked.json() == session_read.json()


async def test_reading_a_turn_changes_nothing_in_the_room(
    client, db_session: AsyncSession, per_request, fakes
) -> None:
    team, credential = await a_claimed_device(db_session, email="reads@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=team.id)
    headers = team_headers(credential)
    stored = await _post_a_turn(client, session.id, headers, "gravado")
    assert stored.status_code == 200, stored.text[:300]
    fakes["model"].held.clear()
    fakes["model"].thinking.clear()
    flying = asyncio.create_task(_post_a_turn(client, session.id, headers, "em-voo"))
    await asyncio.wait_for(fakes["model"].thinking.wait(), timeout=5)

    async def _room_now() -> tuple[int, list[dict[str, Any]]]:
        async with per_request() as fresh:
            reread = await get_session(fresh, session.id)
        return reread.version, list(reread.messages)

    before_room, before_calls = await _room_now(), _calls(fakes)
    seen = [
        await _look_at(client, session.id, headers, turn_id)
        for turn_id in ("gravado", "em-voo", "desconhecido")
    ]
    after_room, after_calls = await _room_now(), _calls(fakes)
    fakes["model"].held.set()
    await flying

    assert [r.status_code for r in seen] == [200, 202, 404]
    assert after_room == before_room
    assert after_calls == before_calls
