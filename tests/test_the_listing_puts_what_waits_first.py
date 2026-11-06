"""The team listing answers the teams with something waiting first, each group by its activity."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.core.room_enums import HaltKind
from app.db.models.internalization_room import (
    IRQuestion,
    IRQuestionStatus,
    IRSession,
    IRSessionStatus,
)
from app.services.auth.issue_tokens import issue_tokens
from app.services.device.create_device import create_device
from tests.baker import (
    grant_facilitator_app_role,
    grant_room_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.halt_harness import attend as attend_the_room
from tests.hard_stretch_harness import Facilitator

TEAMS = "/api/facilitator/teams"
ROOM = "/api/internalization-room"
DEVICES = "/api/facilitator/devices"
SESSIONS = "/api/facilitator/sessions"
PASSAGE = "P01"

NEWEST = timedelta(days=1)
NEWER = timedelta(days=2)
OLDER = timedelta(days=10)
OLDEST = timedelta(days=40)
NOW = datetime.now(UTC)

_made = 0


def ago(moment: timedelta) -> datetime:
    return NOW - moment


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.facilitator.devices import facilitator_devices_router
    from app.api.facilitator.sessions import facilitator_sessions_router
    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(facilitator_teams_router, prefix=TEAMS)
    test_app.include_router(facilitator_devices_router, prefix=DEVICES)
    test_app.include_router(facilitator_sessions_router, prefix=SESSIONS)
    test_app.include_router(room_router, prefix=ROOM)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def a_team(db: AsyncSession, name: str):
    global _made
    _made += 1
    language = await make_language(db, name=name, code=f"t{_made % 100:02d}")
    return await make_project(db, language.id, name=name)


async def a_facilitator(db: AsyncSession, *teams) -> tuple[str, dict[str, str]]:
    global _made
    _made += 1
    user = await make_user(db, email=f"facilitador-{_made}@example.com")
    for team in teams:
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return user.id, {"Authorization": f"Bearer {access}"}


async def a_consultant(db: AsyncSession) -> dict[str, str]:
    user = await make_user(db, email="consultora@example.com")
    await grant_room_app_role(db, user.id, "consultant")
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def a_session(
    db: AsyncSession,
    team,
    *,
    when: timedelta,
    pericope: str = PASSAGE,
    status: IRSessionStatus = IRSessionStatus.IN_PROGRESS,
    warned: bool = False,
    ended: bool = False,
) -> IRSession:
    at = ago(when)
    session = IRSession(
        pericope=pericope,
        status=status,
        project_id=team.id,
        messages=[{"role": "team", "text": "oi"}, {"role": "guide", "text": "ok"}],
        coverage_state={},
        back_translation={},
        created_at=at,
        updated_at=at,
        warned_at=at if warned else None,
        ended_at=at if ended else None,
        halt_kind=HaltKind.BLOCKING.value if status is IRSessionStatus.NEEDS_PERSON else None,
        halts_raised=1 if status is IRSessionStatus.NEEDS_PERSON else 0,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def a_halted_session(db: AsyncSession, team, *, when: timedelta, **more) -> IRSession:
    return await a_session(db, team, when=when, status=IRSessionStatus.NEEDS_PERSON, **more)


async def a_raised_hand(db: AsyncSession, team, *, when: timedelta) -> None:
    db.add(
        IRQuestion(
            device_id="aparelho",
            session_id="sessao",
            pericope=PASSAGE,
            audio_key="pergunta.m4a",
            status=IRQuestionStatus.OPEN,
            project_id=team.id,
            created_at=ago(when),
        )
    )
    await db.commit()


async def a_halted_tablet(db: AsyncSession, team, *, unlinked: bool = False):
    minted = await create_device(db)
    device = minted.device
    device.project_id = team.id
    device.claimed_at = datetime.now(UTC)
    device.needs_person_since = datetime.now(UTC)
    if unlinked:
        device.unlinked_at = datetime.now(UTC)
    await db.commit()
    return device


async def the_order(client: httpx.AsyncClient, headers: dict[str, str], **params) -> list[str]:
    answer = await client.get(TEAMS, headers=headers, params=params)
    assert answer.status_code == 200, answer.text[:300]
    return [team["name"] for team in answer.json()["teams"]]


async def test_a_team_with_one_halted_session_comes_before_a_team_with_newer_activity(
    client, db_session
):
    halted = await a_team(db_session, "Parada")
    quiet = await a_team(db_session, "Ativa")
    await a_halted_session(db_session, halted, when=OLDER)
    await a_session(db_session, quiet, when=NEWEST)
    _user, headers = await a_facilitator(db_session, halted, quiet)

    assert await the_order(client, headers) == ["Parada", "Ativa"]


async def test_a_halt_on_a_closed_passage_waits(client, db_session):
    closed = await a_team(db_session, "Fechada")
    quiet = await a_team(db_session, "Ativa")
    await a_halted_session(db_session, closed, when=OLDER, ended=True)
    await a_session(db_session, quiet, when=NEWEST)
    _user, headers = await a_facilitator(db_session, closed, quiet)

    assert await the_order(client, headers) == ["Fechada", "Ativa"]


async def test_a_team_whose_only_waiting_thing_is_a_halted_tablet_is_in_the_first_group(
    client, db_session
):
    tablet = await a_team(db_session, "Tablet parado")
    quiet = await a_team(db_session, "Ativa")
    await a_halted_tablet(db_session, tablet)
    await a_session(db_session, quiet, when=NEWEST)
    _user, headers = await a_facilitator(db_session, tablet, quiet)

    assert await the_order(client, headers) == ["Tablet parado", "Ativa"]


async def test_a_room_under_a_standing_warning_waits_as_a_halted_one_does(client, db_session):
    warned = await a_team(db_session, "Avisada")
    quiet = await a_team(db_session, "Ativa")
    await a_session(db_session, warned, when=OLDER, warned=True)
    await a_session(db_session, quiet, when=NEWEST)
    _user, headers = await a_facilitator(db_session, warned, quiet)

    assert await the_order(client, headers) == ["Avisada", "Ativa"]


async def _a_finished_passage(client, db, team, headers) -> None:
    await a_session(db, team, when=OLDER, status=IRSessionStatus.DONE)


async def _a_warning_on_a_finished_passage(client, db, team, headers) -> None:
    await a_session(db, team, when=OLDER, status=IRSessionStatus.DONE, warned=True)


async def _a_zeroed_sessions_halt(client, db, team, headers) -> None:
    await a_halted_session(db, team, when=OLDER)
    zeroed = await client.post(
        f"{ROOM}/facilitator/projects/{team.id}/passages/{PASSAGE}/archive", headers=headers
    )
    assert zeroed.status_code == 200, zeroed.text[:300]


async def _an_unlinked_tablets_halt(client, db, team, headers) -> None:
    await a_session(db, team, when=OLDER)
    await a_halted_tablet(db, team, unlinked=True)


@pytest.mark.parametrize(
    "what_it_holds",
    [
        pytest.param(_a_finished_passage, id="a finished passage"),
        pytest.param(_a_warning_on_a_finished_passage, id="a warning on a finished passage"),
        pytest.param(_a_zeroed_sessions_halt, id="a zeroed session's halt"),
        pytest.param(_an_unlinked_tablets_halt, id="an unlinked tablet's halt"),
    ],
)
async def test_what_no_longer_waits_on_anybody_does_not_place_a_team(
    client,
    db_session,
    what_it_holds: Callable[..., Awaitable[None]],
):
    holder = await a_team(db_session, "Antiga")
    quiet = await a_team(db_session, "Recente")
    await a_session(db_session, quiet, when=NEWEST)
    _user, headers = await a_facilitator(db_session, holder, quiet)

    await what_it_holds(client, db_session, holder, headers)

    assert await the_order(client, headers) == ["Recente", "Antiga"]


async def _a_halted_room(db: AsyncSession, team) -> IRSession:
    return await a_halted_session(db, team, when=OLDER)


async def _a_warned_room(db: AsyncSession, team) -> IRSession:
    return await a_session(db, team, when=OLDER, warned=True)


async def _a_tablet_halted(db: AsyncSession, team):
    await a_session(db, team, when=OLDER)
    return await a_halted_tablet(db, team)


async def _attending_the_room(client, session: IRSession, who: Facilitator) -> httpx.Response:
    return await attend_the_room(client, session.id, who)


async def _attending_the_tablet(client, device, who: Facilitator) -> httpx.Response:
    queue = await client.get(f"{ROOM}/facilitator/sessions", headers=who.headers)
    since = next(row["since"] for row in queue.json()["devices"] if row["device_id"] == device.id)
    return await client.post(
        f"{DEVICES}/{device.id}/attended",
        headers=who.headers,
        params={"needs_person_since": since},
    )


@pytest.mark.parametrize(
    ("what_waits", "marking_it_attended"),
    [
        pytest.param(_a_halted_room, _attending_the_room, id="a halted session"),
        pytest.param(_a_warned_room, _attending_the_room, id="a room under a warning"),
        pytest.param(_a_tablet_halted, _attending_the_tablet, id="a halted tablet"),
    ],
)
async def test_once_marked_attended_the_next_answer_puts_the_team_back_in_the_second_group(
    client,
    db_session,
    what_waits: Callable[..., Awaitable],
    marking_it_attended: Callable[..., Awaitable[httpx.Response]],
):
    team = await a_team(db_session, "Atendida")
    quiet = await a_team(db_session, "Recente")
    await a_session(db_session, quiet, when=NEWEST)
    user_id, headers = await a_facilitator(db_session, team, quiet)
    waiting = await what_waits(db_session, team)
    assert await the_order(client, headers) == ["Atendida", "Recente"]

    who = Facilitator(user_id, team.id, headers, team_name=team.name)
    attended = await marking_it_attended(client, waiting, who)

    assert attended.status_code == 200, attended.text[:300]
    assert await the_order(client, headers) == ["Recente", "Atendida"]


async def test_how_many_questions_wait_does_not_place_a_team(client, db_session):
    many = await a_team(db_session, "Tres perguntas antigas")
    one = await a_team(db_session, "Uma pergunta recente")
    for _ in range(3):
        await a_raised_hand(db_session, many, when=OLDER)
    await a_raised_hand(db_session, one, when=NEWER)
    _user, headers = await a_facilitator(db_session, many, one)

    assert await the_order(client, headers) == ["Uma pergunta recente", "Tres perguntas antigas"]


async def test_a_team_with_many_halts_appears_once_placed_by_its_activity(client, db_session):
    many = await a_team(db_session, "Muitas paradas")
    hand = await a_team(db_session, "Uma pergunta recente")
    quiet = await a_team(db_session, "Recente")
    await a_halted_session(db_session, many, when=OLDER, pericope="P01")
    await a_halted_session(db_session, many, when=OLDEST, pericope="P02")
    await a_halted_tablet(db_session, many)
    await a_raised_hand(db_session, hand, when=NEWER)
    await a_session(db_session, quiet, when=NEWEST)
    _user, headers = await a_facilitator(db_session, many, hand, quiet)

    assert await the_order(client, headers) == [
        "Uma pergunta recente",
        "Muitas paradas",
        "Recente",
    ]


async def test_a_team_never_active_comes_last_in_its_group(client, db_session):
    tablet = await a_team(db_session, "Nunca ativa com tablet parado")
    never = await a_team(db_session, "Nunca ativa")
    quiet = await a_team(db_session, "Antiga sem espera")
    hand = await a_team(db_session, "Antiga com pergunta")
    await a_halted_tablet(db_session, tablet)
    await a_session(db_session, quiet, when=NEWEST)
    await a_raised_hand(db_session, hand, when=OLDEST)
    _user, headers = await a_facilitator(db_session, tablet, never, quiet, hand)

    assert await the_order(client, headers) == [
        "Antiga com pergunta",
        "Nunca ativa com tablet parado",
        "Antiga sem espera",
        "Nunca ativa",
    ]


async def test_teams_level_on_group_and_activity_come_in_the_order_of_their_names(
    client, db_session
):
    waiting = [await a_team(db_session, name) for name in ("Yara", "Ítala")]
    quiet = [await a_team(db_session, name) for name in ("Zeta", "Bravo", "Ábaco")]
    for team in waiting:
        await a_halted_session(db_session, team, when=OLDER)
    for team in quiet:
        await a_session(db_session, team, when=OLDER)
    _user, headers = await a_facilitator(db_session, *waiting, *quiet)

    assert await the_order(client, headers) == ["Ítala", "Yara", "Ábaco", "Bravo", "Zeta"]


async def test_a_consultant_and_a_facilitator_of_the_same_teams_get_the_same_order(
    client, db_session
):
    room = await a_team(db_session, "Sala parada")
    tablet = await a_team(db_session, "Tablet parado")
    quiet = await a_team(db_session, "Recente")
    never = await a_team(db_session, "Nunca ativa")
    await a_halted_session(db_session, room, when=OLDER)
    await a_session(db_session, tablet, when=OLDEST)
    await a_halted_tablet(db_session, tablet)
    await a_session(db_session, quiet, when=NEWEST)
    _user, facilitator = await a_facilitator(db_session, room, tablet, quiet, never)
    consultant = await a_consultant(db_session)

    expected = ["Sala parada", "Tablet parado", "Recente", "Nunca ativa"]
    assert await the_order(client, facilitator) == expected
    assert await the_order(client, consultant) == expected


async def test_the_search_narrows_first_and_the_order_applies_to_what_is_left(client, db_session):
    halted = await a_team(db_session, "Terena Norte")
    quiet = await a_team(db_session, "Terena Sul")
    other = await a_team(db_session, "Kaiwa")
    await a_halted_session(db_session, halted, when=OLDER)
    await a_session(db_session, quiet, when=NEWER)
    await a_halted_session(db_session, other, when=NEWEST)
    _user, headers = await a_facilitator(db_session, halted, quiet, other)

    assert await the_order(client, headers, search="terena") == ["Terena Norte", "Terena Sul"]


async def test_the_filter_narrows_first_and_the_order_applies_to_what_is_left(client, db_session):
    many = await a_team(db_session, "Tres perguntas antigas")
    one = await a_team(db_session, "Uma pergunta recente")
    halted = await a_team(db_session, "Parada sem pergunta")
    for _ in range(3):
        await a_raised_hand(db_session, many, when=OLDER)
    await a_raised_hand(db_session, one, when=NEWER)
    await a_halted_session(db_session, halted, when=NEWEST)
    _user, headers = await a_facilitator(db_session, many, one, halted)

    assert await the_order(client, headers, filter="with_hands") == [
        "Uma pergunta recente",
        "Tres perguntas antigas",
    ]


async def test_a_halt_on_a_team_the_reader_may_not_read_leaves_their_order_as_it_was(
    client, db_session
):
    newer = await a_team(db_session, "Minha recente")
    older = await a_team(db_session, "Minha antiga")
    outside = await a_team(db_session, "De outra pessoa")
    await a_session(db_session, newer, when=NEWER)
    await a_session(db_session, older, when=OLDER)
    await a_halted_session(db_session, outside, when=NEWEST)
    await a_halted_tablet(db_session, outside)
    _user, headers = await a_facilitator(db_session, newer, older)

    assert await the_order(client, headers) == ["Minha recente", "Minha antiga"]


async def _a_team_with_everything_waiting(db: AsyncSession, name: str):
    team = await a_team(db, name)
    await a_raised_hand(db, team, when=NEWER)
    await a_halted_session(db, team, when=OLDER)
    await a_halted_tablet(db, team)
    return team


async def test_the_listing_of_ten_teams_makes_as_many_statements_as_the_listing_of_one(
    client, db_session, test_engine
):
    statements: list[str] = []

    @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        first = await _a_team_with_everything_waiting(db_session, "Equipe 0")
        user_id, headers = await a_facilitator(db_session, first)
        assert len(await the_order(client, headers)) == 1
        statements.clear()
        assert len(await the_order(client, headers)) == 1
        for_one = len(statements)

        for n in range(1, 10):
            team = await _a_team_with_everything_waiting(db_session, f"Equipe {n}")
            await make_project_user_access(
                db_session, team.id, user_id, role=ProjectRole.FACILITATOR
            )
        statements.clear()
        assert len(await the_order(client, headers)) == 10
        for_ten = len(statements)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _count)

    assert for_one == for_ten
