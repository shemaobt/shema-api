from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import background
from app.services.internalization_room.sessions import create_session, get_session
from tests.baker import make_app, make_role
from tests.earlier_passages_harness import a_room_whose_guide_is_scripted, a_session_per_request
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    a_claimed_device,
    at_the_desk,
    ready_session,
    team_headers,
    team_release,
)
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_team_says
from tests.text_seam_harness import ScriptedAgent

EN = "\N{EN DASH}"
LINE = (
    "EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1" + EN + "5. "
    "Started, not approved yet: Ruth 1:6" + EN + "14. "
    "Not worked yet: Ruth 1:15" + EN + "18."
)
OLD_SHAPE = [
    {"role": "guide", "text": "Abertura antiga.", "at": "2026-09-01T12:00:00+00:00"},
    {"role": "team", "text": "resposta antiga", "at": "2026-09-01T12:01:00+00:00"},
    {
        "role": "guide",
        "text": "Linha antiga.",
        "at": "2026-09-01T12:01:00+00:00",
        "outcome": "pass",
        "redrafts": 0,
    },
]
STORED = {"P01": "approved", "P02": "started", "P03": "not_worked"}


@pytest.fixture()
def agent(monkeypatch: pytest.MonkeyPatch) -> ScriptedAgent:
    return a_room_whose_guide_is_scripted(monkeypatch)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return a_session_per_request(test_engine)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, agent, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def the_desk_list(db_session: AsyncSession, per_request):
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        async with per_request() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def opened(client: httpx.AsyncClient, tablet: str, pericope: str) -> str:
    answered = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": pericope},
    )
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()["session_id"]


async def turns_of(client: httpx.AsyncClient, desk: dict[str, str], session_id: str) -> list[Any]:
    answered = await client.get(f"{PREFIX}/facilitator/sessions/{session_id}/turns", headers=desk)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()["turns"]


async def desk_row(
    the_desk_list: httpx.AsyncClient, desk: dict[str, str], team_id: str, session_id: str
) -> dict[str, Any]:
    answered = await the_desk_list.get(
        "/api/facilitator/sessions", headers=desk, params={"team_id": team_id}
    )
    assert answered.status_code == 200, answered.text[:300]
    (row,) = [s for s in answered.json()["sessions"] if s["session_id"] == session_id]
    return row


def without_at(stamp: dict[str, str] | None) -> dict[str, str] | None:
    return None if stamp is None else {k: v for k, v in stamp.items() if k != "at"}


async def history(client: httpx.AsyncClient, db: AsyncSession, team: Any, tablet: str) -> Any:
    p01 = await ready_session(db, pericope="P01", project_id=team.id)
    approval = await client.post(team_release(p01.id), headers=team_headers(tablet))
    assert approval.status_code == 200, approval.text[:300]
    return await ready_session(db, pericope="P02", project_id=team.id)


async def approve(client: httpx.AsyncClient, tablet: str, session: Any) -> None:
    approval = await client.post(team_release(session.id), headers=team_headers(tablet))
    assert approval.status_code == 200, approval.text[:300]


async def row_stamp(per_request: async_sessionmaker[AsyncSession], session_id: str) -> Any:
    async with per_request() as fresh:
        return (await get_session(fresh, session_id)).earlier_passages


async def six_minutes_old(per_request: async_sessionmaker[AsyncSession], session_id: str) -> None:
    stamp = await row_stamp(per_request, session_id)
    aged = {**stamp, "at": (datetime.now(UTC) - timedelta(minutes=6)).isoformat()}
    async with per_request() as fresh:
        await fresh.execute(
            update(IRSession).where(IRSession.id == session_id).values(earlier_passages=aged)
        )
        await fresh.commit()


async def test_a_session_on_p04_keeps_the_stamp_on_its_opening_turn_and_the_desk_reads_it_for_the_session(  # noqa: E501
    client, the_desk_list, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    await history(client, db_session, team, tablet)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session_id = await opened(client, tablet, "P04")
    await the_room_opens(client, tablet, session_id)

    (opening,) = await turns_of(client, desk, session_id)
    stamp = opening["voice"]["earlier_passages"]

    assert without_at(stamp) == STORED
    assert datetime.fromisoformat(stamp["at"]).tzinfo is not None
    assert (await desk_row(the_desk_list, desk, team.id, session_id))["earlier_passages"] == stamp


async def test_a_team_that_approves_p02_during_the_session_is_told_so_on_a_later_turn_while_the_opening_still_says_started(  # noqa: E501
    client, the_desk_list, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    p02 = await history(client, db_session, team, tablet)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session_id = await opened(client, tablet, "P04")
    await the_room_opens(client, tablet, session_id)
    await six_minutes_old(per_request, session_id)
    await approve(client, tablet, p02)
    await the_team_says(client, tablet, session_id, str(uuid.uuid4()))
    await the_team_says(client, tablet, session_id, str(uuid.uuid4()))

    turns = await turns_of(client, desk, session_id)
    voices = [turn["voice"]["earlier_passages"] for turn in turns]

    assert without_at(voices[0]) == STORED
    assert without_at(voices[-1]) == {**STORED, "P02": "approved"}
    row = await desk_row(the_desk_list, desk, team.id, session_id)
    assert row["earlier_passages"] == voices[0]


async def test_a_team_that_approves_p02_after_the_session_changes_neither_the_turns_nor_the_desk(
    client, the_desk_list, db_session, per_request, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    p02 = await history(client, db_session, team, tablet)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session_id = await opened(client, tablet, "P04")
    await the_room_opens(client, tablet, session_id)
    await the_team_says(client, tablet, session_id, str(uuid.uuid4()))
    turns_before = await turns_of(client, desk, session_id)
    row_before = await desk_row(the_desk_list, desk, team.id, session_id)
    assert without_at(turns_before[0]["voice"]["earlier_passages"]) == STORED

    await approve(client, tablet, p02)
    await background.read_the_earlier_passages_again(session_id=session_id)

    assert (await row_stamp(per_request, session_id))["P02"] == "approved"
    assert await turns_of(client, desk, session_id) == turns_before
    assert await desk_row(the_desk_list, desk, team.id, session_id) == row_before


async def test_a_turn_stored_before_this_change_reads_no_stamp_even_when_the_session_row_has_one(
    client, the_desk_list, db_session, per_request, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session = await create_session(db_session, language="pt", pericope="P04", project_id=team.id)
    session.messages = OLD_SHAPE
    session.earlier_passages = {**STORED, "at": datetime.now(UTC).isoformat()}
    await db_session.commit()

    turns = await turns_of(client, desk, session.id)

    assert [turn["voice"]["earlier_passages"] for turn in turns] == [None, None]
    assert (await desk_row(the_desk_list, desk, team.id, session.id))["earlier_passages"] is None


async def test_a_panorama_session_carries_no_stamp_on_its_turns_or_on_the_desk(
    client, the_desk_list, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session_id = await opened(client, tablet, "OV-Ruth")
    await the_room_opens(client, tablet, session_id)

    (opening,) = await turns_of(client, desk, session_id)

    assert opening["voice"]["earlier_passages"] is None
    assert (await desk_row(the_desk_list, desk, team.id, session_id))["earlier_passages"] is None


async def test_a_session_on_the_books_first_passage_carries_no_stamp(
    client, the_desk_list, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session_id = await opened(client, tablet, "P01")
    await the_room_opens(client, tablet, session_id)

    (opening,) = await turns_of(client, desk, session_id)

    assert opening["voice"]["earlier_passages"] is None
    assert (await desk_row(the_desk_list, desk, team.id, session_id))["earlier_passages"] is None


async def test_the_stamp_a_turn_keeps_is_the_one_the_voices_earlier_passages_line_was_built_from(
    client, db_session, room_app, agent
) -> None:
    team, tablet = await a_claimed_device(db_session)
    await history(client, db_session, team, tablet)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session_id = await opened(client, tablet, "P04")
    await the_room_opens(client, tablet, session_id)

    (opening,) = await turns_of(client, desk, session_id)

    assert LINE in agent.guide_systems[0].splitlines()
    assert without_at(opening["voice"]["earlier_passages"]) == STORED


async def test_a_session_not_yet_opened_carries_no_stamp_on_the_desk(
    client, the_desk_list, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session = await create_session(db_session, language="pt", pericope="P04", project_id=team.id)
    session.messages = [{"role": "team", "text": "oi", "at": "2026-09-01T12:01:00+00:00"}]
    session.earlier_passages = {**STORED, "at": datetime.now(UTC).isoformat()}
    await db_session.commit()

    row = await desk_row(the_desk_list, desk, team.id, session.id)

    assert row["earlier_passages"] is None
