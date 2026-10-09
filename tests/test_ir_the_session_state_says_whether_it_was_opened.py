"""ENG-1464 — the session state says whether the session was opened.

A session is opened once it holds a Guide line. The tablet reads the state to decide whether
to ask the Opening, so a new session reads false, a session whose Opening landed reads true on
the read and on the open door alike, and a room note or a team entry alone does not open it.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession
from tests.opening_harness import a_scripted_room, another_tablet_of, the_tablet_opens
from tests.release_harness import PREFIX, P, a_claimed_device, team_headers
from tests.room_harness import room_client
from tests.tablet_turn_harness import the_room_opens

BODY = {"pericope": P, "language": "pt"}


@pytest.fixture(autouse=True)
def script(monkeypatch: pytest.MonkeyPatch):
    return a_scripted_room(monkeypatch)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def the_tablet_reads(client: httpx.AsyncClient, credential: str, session_id: str) -> Any:
    read = await client.get(f"{PREFIX}/sessions/{session_id}", headers=team_headers(credential))
    assert read.status_code == 200, read.text[:300]
    return read.json()


async def the_row_holds(
    per_request: async_sessionmaker[AsyncSession], session_id: str, messages: list[dict]
) -> None:
    async with per_request() as other_instance:
        await other_instance.execute(
            update(IRSession)
            .where(IRSession.id == session_id)
            .values(messages=messages, updated_at=IRSession.updated_at)
        )
        await other_instance.commit()


async def test_a_session_read_says_a_new_session_is_not_opened_and_opened_once_its_opening_landed(
    client, db_session
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    session_id = (await the_tablet_opens(client, tablet, BODY))["session_id"]

    assert (await the_tablet_reads(client, tablet, session_id))["opened"] is False

    await the_room_opens(client, tablet, session_id)

    assert (await the_tablet_reads(client, tablet, session_id))["opened"] is True


async def test_opening_a_session_the_team_already_opened_answers_opened_in_the_same_answer(
    client, db_session
) -> None:
    team, first_tablet = await a_claimed_device(db_session)
    second_tablet = await another_tablet_of(db_session, team)
    first = await the_tablet_opens(client, first_tablet, BODY)
    await the_room_opens(client, first_tablet, first["session_id"])

    joined = await the_tablet_opens(client, second_tablet, BODY)

    assert joined["session_id"] == first["session_id"]
    assert joined["opened"] is True


async def test_a_session_whose_only_entry_is_a_room_note_is_not_opened(
    client, db_session, per_request
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    session_id = (await the_tablet_opens(client, tablet, BODY))["session_id"]
    await the_row_holds(
        per_request, session_id, [{"role": "room", "text": "[a sessão acabou de começar]"}]
    )

    assert (await the_tablet_reads(client, tablet, session_id))["opened"] is False


async def test_a_session_holding_a_room_note_and_a_team_entry_and_no_guide_line_is_not_opened(
    client, db_session, per_request
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    session_id = (await the_tablet_opens(client, tablet, BODY))["session_id"]
    await the_row_holds(
        per_request,
        session_id,
        [
            {"role": "room", "text": "[a sessão acabou de começar]"},
            {"role": "team", "text": "Noemi voltou para Belém"},
        ],
    )

    assert (await the_tablet_reads(client, tablet, session_id))["opened"] is False
