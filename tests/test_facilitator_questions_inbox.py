"""ENG-452 — the inbox route: whose questions, in which state, and how many exist.

The route was mounted and unusable. It accepted no parameter at all, answered `open` only,
and answered it **installation-wide** — a facilitator read the hands of teams that were not
theirs. That is the case this file leads with, because it is a leak and not a missing
feature.

The rest is the shape a page has to have to be honest. A route that truncates and does not
say how many exist is incomplete by construction: the only recourse left to a consumer is
to count what arrived, which is the defect ENG-485 closed on the Desk one collection along.
So the count travels beside the page, it counts the scope and not the page, and the order is
served — because the order is what decides which questions fit in the page at all, and a
client re-sorting a truncated page is arranging an arbitrary sample with no way of knowing.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

INBOX_URL = "/api/internalization-room/facilitator/questions"

#: Far enough apart that "newest first" is a claim about the order and not about the clock's
#: resolution — SQLite's `CURRENT_TIMESTAMP` counts in whole seconds.
A_WHILE = timedelta(hours=1)


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.internalization_room.questions import router as questions_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(questions_router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


_made = 0


async def a_team(db: AsyncSession, *, name: str):
    """A project, which is what a team is (D-16), with a language of its own."""
    global _made
    _made += 1
    language = await make_language(db, name=name, code=f"q{_made % 100:02d}")
    return await make_project(db, language.id, name=name)


async def a_facilitator(db: AsyncSession, *teams, email: str = "facilitadora@example.com"):
    user = await make_user(db, email=email)
    for team in teams:
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    return user, await auth_header(db, user)


async def a_hand(
    db: AsyncSession,
    team,
    *,
    status: IRQuestionStatus = IRQuestionStatus.OPEN,
    ago: timedelta = A_WHILE,
    device: str = "aparelho",
    pericope: str = "P01",
) -> IRQuestion:
    question = IRQuestion(
        device_id=device,
        session_id="sessao",
        pericope=pericope,
        audio_key="pergunta.m4a",
        status=status,
        project_id=team.id if team is not None else None,
        created_at=datetime.now(UTC) - ago,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


async def read(client, headers, **params) -> dict:
    response = await client.get(INBOX_URL, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def ids(payload: dict) -> list[str]:
    return [question["question_id"] for question in payload["questions"]]


@pytest.mark.asyncio
async def test_without_a_team_id_only_the_callers_own_teams_are_read(client, db_session):
    """The leak this slice exists to close, stated first.

    The route answered every open question in the installation. A facilitator has one team
    and read the hands of every other one, which is not a shortage of filtering — it is a
    person seeing work that was never addressed to them.
    """
    mine = await a_team(db_session, name="Equipe Terena")
    theirs = await a_team(db_session, name="Equipe Guarani")
    ours = await a_hand(db_session, mine)
    await a_hand(db_session, theirs)
    _user, headers = await a_facilitator(db_session, mine)

    payload = await read(client, headers)

    assert ids(payload) == [ours.id]


@pytest.mark.asyncio
async def test_a_team_that_is_not_yours_is_refused_exactly_as_one_that_is_absent(
    client, db_session
):
    """The parameter filters and does not grant — and it refuses in one sentence for both.

    A facilitator who could tell "not yours" from "no such thing" could map an installation
    by asking about ids, and closing that at one door while leaving it open at another closes
    nothing. It is the rule the team routes already hold.
    """
    mine = await a_team(db_session, name="Equipe Terena")
    theirs = await a_team(db_session, name="Equipe Guarani")
    _user, headers = await a_facilitator(db_session, mine)

    not_yours = await client.get(INBOX_URL, headers=headers, params={"team_id": theirs.id})
    absent = await client.get(INBOX_URL, headers=headers, params={"team_id": "nao-existe"})

    assert not_yours.status_code == 404, not_yours.text
    assert (not_yours.status_code, not_yours.json()) == (absent.status_code, absent.json())


@pytest.mark.asyncio
async def test_a_team_id_narrows_to_that_team(client, db_session):
    first = await a_team(db_session, name="Equipe Terena")
    second = await a_team(db_session, name="Equipe Guarani")
    here = await a_hand(db_session, first)
    await a_hand(db_session, second)
    _user, headers = await a_facilitator(db_session, first, second)

    payload = await read(client, headers, team_id=first.id)

    assert ids(payload) == [here.id]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "wanted",
    [IRQuestionStatus.OPEN, IRQuestionStatus.ANSWERED, IRQuestionStatus.RESOLVED],
)
async def test_each_of_the_three_card_states_can_be_asked_for(client, db_session, wanted):
    """`resolved` is a state of the card and not a reply: the facilitator will speak to the
    team in person and nothing about it reaches the app. It is still a card the Desk draws.
    """
    team = await a_team(db_session, name="Equipe Terena")
    held = {
        state: await a_hand(db_session, team, status=state)
        for state in (
            IRQuestionStatus.OPEN,
            IRQuestionStatus.ANSWERED,
            IRQuestionStatus.RESOLVED,
        )
    }
    _user, headers = await a_facilitator(db_session, team)

    payload = await read(client, headers, status=wanted.value)

    assert ids(payload) == [held[wanted].id]
    assert [question["status"] for question in payload["questions"]] == [wanted.value]


@pytest.mark.asyncio
async def test_without_a_status_the_three_states_arrive_together(client, db_session):
    team = await a_team(db_session, name="Equipe Terena")
    for state in IRQuestionStatus:
        await a_hand(db_session, team, status=state)
    _user, headers = await a_facilitator(db_session, team)

    payload = await read(client, headers)

    assert {question["status"] for question in payload["questions"]} == {
        state.value for state in IRQuestionStatus
    }


@pytest.mark.asyncio
async def test_open_first_and_the_newest_first_inside_each_group(client, db_session):
    """RF-04's inbox, served. The queue on top, the record below it by recency alone.

    Served rather than left to the client because the order decides which questions fit in
    the page: sorted after the cut, the facilitator is handed an arbitrary sample.
    """
    team = await a_team(db_session, name="Equipe Terena")
    old_open = await a_hand(db_session, team, ago=timedelta(days=4))
    new_open = await a_hand(db_session, team, ago=timedelta(hours=1))
    old_settled = await a_hand(
        db_session, team, status=IRQuestionStatus.RESOLVED, ago=timedelta(days=9)
    )
    new_settled = await a_hand(
        db_session, team, status=IRQuestionStatus.ANSWERED, ago=timedelta(days=2)
    )
    _user, headers = await a_facilitator(db_session, team)

    payload = await read(client, headers)

    assert ids(payload) == [new_open.id, old_open.id, new_settled.id, old_settled.id]


@pytest.mark.asyncio
async def test_the_total_counts_the_scope_and_not_the_page(client, db_session):
    """The whole reason the number travels: it is allowed to be larger than the array.

    A page of one beside a total of three is correct. Deriving the count from the page is
    the defect — the facilitator reads it on the team list and again inside the Desk, and
    the smaller of two numbers that never look broken is the one that gets believed.
    """
    team = await a_team(db_session, name="Equipe Terena")
    for _ in range(3):
        await a_hand(db_session, team)
    _user, headers = await a_facilitator(db_session, team)

    payload = await read(client, headers, limit=1)

    assert len(payload["questions"]) == 1
    assert payload["open_total"] == 3


@pytest.mark.asyncio
async def test_the_total_counts_open_hands_whatever_state_was_asked_for(client, db_session):
    """It answers "how many hands are up", not "how many rows matched"."""
    team = await a_team(db_session, name="Equipe Terena")
    await a_hand(db_session, team)
    await a_hand(db_session, team)
    settled = await a_hand(db_session, team, status=IRQuestionStatus.RESOLVED)
    _user, headers = await a_facilitator(db_session, team)

    payload = await read(client, headers, status="resolved")

    assert ids(payload) == [settled.id]
    assert payload["open_total"] == 2


@pytest.mark.asyncio
async def test_the_total_is_scoped_like_the_page_is(client, db_session):
    mine = await a_team(db_session, name="Equipe Terena")
    theirs = await a_team(db_session, name="Equipe Guarani")
    await a_hand(db_session, mine)
    await a_hand(db_session, theirs)
    await a_hand(db_session, theirs)
    _user, headers = await a_facilitator(db_session, mine)

    assert (await read(client, headers))["open_total"] == 1


@pytest.mark.asyncio
async def test_the_page_continues_from_the_cursor(client, db_session):
    team = await a_team(db_session, name="Equipe Terena")
    hands = [await a_hand(db_session, team, ago=timedelta(hours=n)) for n in (1, 2, 3)]
    _user, headers = await a_facilitator(db_session, team)

    first = await read(client, headers, limit=2)
    second = await read(client, headers, limit=2, cursor=first["next_cursor"])

    assert ids(first) == [hands[0].id, hands[1].id]
    assert ids(second) == [hands[2].id]


@pytest.mark.asyncio
async def test_a_question_raised_between_two_pages_does_not_shift_the_second(client, db_session):
    """Stable while new questions arrive — which is not a nicety on this route.

    A new question arrives **open, at the top**, so every offset into the list moves by one
    and the second page re-serves a card the facilitator already read while dropping one
    they never saw. Neither looks wrong on screen.
    """
    team = await a_team(db_session, name="Equipe Terena")
    hands = [await a_hand(db_session, team, ago=timedelta(hours=n)) for n in (2, 3, 4)]
    _user, headers = await a_facilitator(db_session, team)

    first = await read(client, headers, limit=2)
    await a_hand(db_session, team, ago=timedelta(minutes=1))
    second = await read(client, headers, limit=2, cursor=first["next_cursor"])

    assert ids(first) == [hands[0].id, hands[1].id]
    assert ids(second) == [hands[2].id]


@pytest.mark.asyncio
async def test_the_last_page_says_it_is_the_last(client, db_session):
    team = await a_team(db_session, name="Equipe Terena")
    await a_hand(db_session, team)
    _user, headers = await a_facilitator(db_session, team)

    assert (await read(client, headers))["next_cursor"] is None


@pytest.mark.asyncio
async def test_a_cursor_that_cannot_be_read_is_refused(client, db_session):
    """Refused rather than answered with the first page.

    A cursor the route silently ignores hands the caller page one while they believe they
    are on page four, and the loop that paged never ends.
    """
    team = await a_team(db_session, name="Equipe Terena")
    await a_hand(db_session, team)
    _user, headers = await a_facilitator(db_session, team)

    response = await client.get(INBOX_URL, headers=headers, params={"cursor": "nao-e-cursor"})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_a_question_belonging_to_no_team_reaches_nobody(client, db_session):
    """The common case today, and the only honest answer to it.

    The room's app does not send its device credential yet, so questions are written with no
    project at all. A row that names no team belongs to none, and there is nothing to
    attribute it to — the route errs low rather than showing it to whoever asks.
    """
    team = await a_team(db_session, name="Equipe Terena")
    await a_hand(db_session, None)
    _user, headers = await a_facilitator(db_session, team)

    payload = await read(client, headers)

    assert ids(payload) == []
    assert payload["open_total"] == 0


@pytest.mark.asyncio
async def test_a_platform_admin_reads_every_team(client, db_session):
    """As on every other facilitator route: they already hold every other power here, and
    scoping the one person able to investigate an installation to nothing leaves nobody
    able to look at it.
    """
    first = await a_team(db_session, name="Equipe Terena")
    second = await a_team(db_session, name="Equipe Guarani")
    await a_hand(db_session, first)
    await a_hand(db_session, second)
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    payload = await read(client, headers)

    assert len(payload["questions"]) == 2
    assert payload["open_total"] == 2


@pytest.mark.asyncio
async def test_the_page_does_not_pay_a_read_per_question(client, db_session, test_engine):
    """What a longer page costs, measured against the page and not against the clock.

    Counting statements does not measure what a statement costs — the installation-wide scan
    this route replaces would have stayed green on any count. What a count does catch is the
    other failure: a page that reads once per row, invisible on a fixture of three and the
    facilitator's whole screen on a team of eighty.
    """
    from sqlalchemy import event

    team = await a_team(db_session, name="Equipe Terena")
    await a_hand(db_session, team)
    _user, headers = await a_facilitator(db_session, team)
    seen: list[str] = []

    @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):
        seen.append(" ".join(statement.split()))

    try:
        await read(client, headers)
        for_one = [statement for statement in seen if "ir_questions" in statement]

        for _ in range(9):
            await a_hand(db_session, team)
        seen.clear()
        payload = await read(client, headers)
        for_ten = [statement for statement in seen if "ir_questions" in statement]
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _record)

    assert len(payload["questions"]) == 10
    assert len(for_ten) == len(for_one), (
        f"a pagina paga por linha: {len(for_one)} -> {len(for_ten)}"
    )
