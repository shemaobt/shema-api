"""ENG-1263 — done is a flag and nothing ends a session on its own.

The cases go through the tablet's open and turn doors and the Desk's history, with the
credentials of real teams, and read what a tablet or the Desk would receive. A session is
`done` once the completion floor was met and stays `done`: the team's next turn is answered,
a second tablet joins it, and a long silence changes nothing. The passage-finished reading
(`active_passage`) decides from the status. Time is moved only through `updated_at`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.progression import active_passage
from app.services.internalization_room.sessions import get_session
from tests.baker import having_finished_the_passage, make_app, make_role
from tests.opening_harness import (
    Script,
    a_scripted_room,
    another_tablet_of,
    desk_routes,
    the_tablet_opens,
    the_team_says,
    the_team_speaks,
)
from tests.release_harness import PREFIX, P, a_claimed_device, at_the_desk
from tests.room_harness import room_client, the_bucket_is_in_memory, the_room_speaks

ROOM_PASSAGES = load_book(ROOM_BOOK)
FIRST = ROOM_PASSAGES[0].pericope_num
SECOND = ROOM_PASSAGES[1].pericope_num


@pytest.fixture()
def script(monkeypatch: pytest.MonkeyPatch) -> Script:
    return a_scripted_room(monkeypatch)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def desk_client(db_session: AsyncSession, per_request):
    async with desk_routes(db_session, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def a_finished_passage(
    client: httpx.AsyncClient,
    per_request: async_sessionmaker[AsyncSession],
    tablet: str,
    pericope: str = P,
) -> dict[str, Any]:
    opened = await the_tablet_opens(client, tablet, {"pericope": pericope})
    async with per_request() as fresh:
        await having_finished_the_passage(fresh, await get_session(fresh, opened["session_id"]))
    return await the_tablet_opens(client, tablet, {"pericope": pericope})


async def the_desk_card(desk_client: httpx.AsyncClient, desk: dict[str, str], team_id: str):
    history = await desk_client.get(f"/api/facilitator/teams/{team_id}/sessions", headers=desk)
    assert history.status_code == 200, history.text[:300]
    [card] = history.json()
    return card


async def what_was_said(
    client: httpx.AsyncClient, desk: dict[str, str], session_id: str, role: str
) -> list[str]:
    read = await client.get(
        f"{PREFIX}/facilitator/sessions/{session_id}/conversation", headers=desk
    )
    assert read.status_code == 200, read.text[:300]
    return [turn["text"] for turn in read.json()["turns"] if turn["role"] == role]


async def test_a_session_that_met_the_floor_is_done_and_the_teams_next_turn_is_answered(
    client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    done = await a_finished_passage(client, per_request, tablet)
    assert done["status"] == "done"

    answered = await the_team_speaks(client, script, tablet, done["session_id"], "Rute foi junto")

    assert answered.status_code == 200, answered.text[:300]
    assert await what_was_said(client, desk, done["session_id"], "team") == ["Rute foi junto"]
    assert len(await what_was_said(client, desk, done["session_id"], "guide")) == 1
    assert (await the_tablet_opens(client, tablet, {"pericope": P}))["status"] == "done"


async def test_a_done_session_stays_done_after_any_number_of_turns(
    client, db_session, per_request, script
) -> None:
    _team, tablet = await a_claimed_device(db_session)
    done = await a_finished_passage(client, per_request, tablet)

    for said in ("Rute foi junto", "Noemi chegou na colheita"):
        await the_team_says(client, script, tablet, done["session_id"], said)
        reopened = await the_tablet_opens(client, tablet, {"pericope": P})
        assert reopened["session_id"] == done["session_id"]
        assert reopened["status"] == "done"


async def test_the_moment_the_floor_was_met_is_stamped_once_and_never_moves(
    client, desk_client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    done = await a_finished_passage(client, per_request, tablet)
    stamped = (await the_desk_card(desk_client, desk, team.id))["ended_at"]
    assert stamped is not None

    for said in ("Rute foi junto", "Noemi chegou na colheita"):
        await the_team_says(client, script, tablet, done["session_id"], said)

    assert (await the_desk_card(desk_client, desk, team.id))["ended_at"] == stamped


async def test_a_second_tablet_of_the_team_opening_a_done_passage_joins_that_session(
    client, db_session, per_request
) -> None:
    team, tablet = await a_claimed_device(db_session)
    done = await a_finished_passage(client, per_request, tablet)
    other = await another_tablet_of(db_session, team)

    joined = await the_tablet_opens(client, other, {"pericope": P})

    assert joined["session_id"] == done["session_id"]
    assert joined["status"] == "done"


async def test_a_session_idle_for_seven_hours_reopened_from_the_menu_is_the_same_session(
    client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P})
    await the_team_says(client, script, tablet, opened["session_id"], "Rute foi junto")
    async with per_request() as fresh:
        await fresh.execute(
            update(IRSession)
            .where(IRSession.id == opened["session_id"])
            .values(updated_at=datetime.now(UTC) - timedelta(hours=7))
        )
        await fresh.commit()

    reopened = await the_tablet_opens(client, tablet, {"pericope": P})

    assert reopened["session_id"] == opened["session_id"]
    assert await what_was_said(client, desk, opened["session_id"], "team") == ["Rute foi junto"]


async def test_a_done_sessions_desk_card_reads_complete_while_the_tablet_sees_it_unchanged(
    client, desk_client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    done = await a_finished_passage(client, per_request, tablet)

    card = await the_desk_card(desk_client, desk, team.id)
    reopened = await the_tablet_opens(client, tablet, {"pericope": P})
    answered = await the_team_speaks(client, script, tablet, done["session_id"], "Rute foi junto")

    assert card["session_id"] == done["session_id"]
    assert card["state"] == "complete"
    assert card["ended_at"] is not None
    assert reopened["session_id"] == done["session_id"]
    assert reopened["status"] == "done"
    assert answered.status_code == 200, answered.text[:300]


async def test_a_passage_counts_as_finished_from_the_sessions_done_status(
    client, db_session, per_request
) -> None:
    team, tablet = await a_claimed_device(db_session)
    team_id = team.id
    done = await a_finished_passage(client, per_request, tablet, FIRST)
    async with per_request() as fresh:
        await fresh.execute(
            update(IRSession).where(IRSession.id == done["session_id"]).values(ended_at=None)
        )
        await fresh.commit()
    db_session.expire_all()

    assert await active_passage(db_session, project_id=team_id) == SECOND


async def test_a_closed_passage_still_carrying_a_halt_stays_finished(
    client, db_session, per_request
) -> None:
    """The row ADR 0044 leaves alone: the old code wrote `needs_person` over `done`."""
    team, tablet = await a_claimed_device(db_session)
    team_id = team.id
    done = await a_finished_passage(client, per_request, tablet, FIRST)
    async with per_request() as fresh:
        await fresh.execute(
            update(IRSession)
            .where(IRSession.id == done["session_id"])
            .values(status=IRSessionStatus.NEEDS_PERSON)
        )
        await fresh.commit()
    db_session.expire_all()

    assert await active_passage(db_session, project_id=team_id) == SECOND
