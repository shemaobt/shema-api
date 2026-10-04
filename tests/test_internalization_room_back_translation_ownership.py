"""ENG-1046: the retro's own routes are answered only for the project that owns the session.

`add_chunk` and `finish` resolved a session by id alone, the way `take_turn` used to before
ENG-1031 gave it `get_session_for_room_caller`, so a device from another project's chunk or
`terminei` ran transcription, the analyst and the Speaker against somebody else's rehearsal
before the room ever turned it away.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import back_translation as bt_api
from app.services.internalization_room.takes import takes_of
from tests.release_harness import KEY, PREFIX, a_claimed_device, team_headers
from tests.room_harness import (
    Analyst,
    Room,
    played_every_part,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)

STRANGER_DEVICE = "tablet-sem-dono"


class _CountingHearing:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *_: Any, **__: Any) -> str:
        self.calls += 1
        return "contado de volta"


@pytest.fixture()
def hearing(monkeypatch: pytest.MonkeyPatch) -> _CountingHearing:
    counter = _CountingHearing()
    monkeypatch.setattr(bt_api, "heard", counter)
    return counter


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture(autouse=True)
def bucket(monkeypatch: pytest.MonkeyPatch):
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _send_chunk(
    client: httpx.AsyncClient, session_id: str, take_id: str, headers: dict[str, str]
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers=headers,
        data={"take_id": take_id, "starts_ms": "0", "ends_ms": "9000"},
        files={"file": ("trecho.m4a", b"a equipe explicou este trecho", "audio/mp4")},
    )


async def _press_terminei(
    client: httpx.AsyncClient, session_id: str, headers: dict[str, str], report: dict[str, Any]
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish", headers=headers, json=report
    )


async def test_a_chunk_from_another_projects_device_is_refused_before_any_work_runs(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    hearing: _CountingHearing,
) -> None:
    owner, owner_credential = await a_claimed_device(db_session, email="owner@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email="stranger@example.com"
    )
    session, parts = await rehearsed_in_parts(db_session, 1, project_id=owner.id)

    refused = await _send_chunk(client, session.id, parts[0].id, team_headers(stranger_credential))
    owner_reply = await _send_chunk(client, session.id, parts[0].id, team_headers(owner_credential))

    assert refused.status_code == 404, refused.text
    assert owner_reply.status_code == 200, owner_reply.text
    assert hearing.calls == 1, "o áudio de outro projeto chegou a ser transcrito"
    stored = await takes_of(db_session, session.id)
    assert len(stored) == 2, "o trecho de outro projeto foi guardado, ou o do dono não foi"


async def test_a_room_key_caller_with_no_device_still_sends_a_chunk_on_a_project_owned_session(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    hearing: _CountingHearing,
) -> None:
    owner, _credential = await a_claimed_device(db_session, email="owner3@example.com")
    session, parts = await rehearsed_in_parts(db_session, 1, project_id=owner.id)

    answered = await _send_chunk(
        client, session.id, parts[0].id, {"X-Room-Key": KEY, "X-Room-Device": STRANGER_DEVICE}
    )

    assert answered.status_code == 200, answered.text
    assert hearing.calls == 1


async def test_a_terminei_from_another_projects_device_is_refused_before_any_work_runs(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
    room: Room,
) -> None:
    owner, owner_credential = await a_claimed_device(db_session, email="owner7@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email="stranger7@example.com"
    )
    session, parts = await rehearsed_in_parts(db_session, 1, project_id=owner.id)
    report = played_every_part([part.id for part in parts])

    refused = await _press_terminei(client, session.id, team_headers(stranger_credential), report)
    owner_reply = await _press_terminei(client, session.id, team_headers(owner_credential), report)

    assert refused.status_code == 404, refused.text
    assert owner_reply.status_code == 200, owner_reply.text
    assert analyst.readings == 1, "o analista leu a sessão de outro projeto"
    assert len(room.said) == 1, "a voz foi sintetizada para o estranho"


async def test_a_room_key_caller_with_no_device_still_finishes_a_project_owned_session(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    owner, _credential = await a_claimed_device(db_session, email="owner8@example.com")
    session, parts = await rehearsed_in_parts(db_session, 1, project_id=owner.id)
    report = played_every_part([part.id for part in parts])

    answered = await _press_terminei(
        client, session.id, {"X-Room-Key": KEY, "X-Room-Device": STRANGER_DEVICE}, report
    )

    assert answered.status_code == 200, answered.text
    assert analyst.readings == 1


async def test_a_remembered_verdict_is_not_replayed_to_another_project(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
) -> None:
    """`already_analysed` serves the verdict the room already reached with no new reading —
    the same shortcut `answered_turn` gives a resend — so a stranger pressing `terminei` a
    second time has to be turned away before that shortcut is ever reached, not just before
    the first reading.
    """
    owner, owner_credential = await a_claimed_device(db_session, email="owner9@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email="stranger9@example.com"
    )
    session, parts = await rehearsed_in_parts(db_session, 1, project_id=owner.id)
    report = played_every_part([part.id for part in parts])

    first = await _press_terminei(client, session.id, team_headers(owner_credential), report)
    assert first.status_code == 200, first.text
    assert analyst.readings == 1

    stranger = await _press_terminei(client, session.id, team_headers(stranger_credential), report)

    assert stranger.status_code == 404, stranger.text
    assert analyst.readings == 1, "o veredito lembrado foi servido para outro projeto"
