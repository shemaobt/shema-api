"""ENG-450 — the book's fourteen passages, each already placed for one team.

`GET /api/facilitator/teams/{id}/pericopes` answers **positions**, not a list. §7 names no
route for the book, so this is new contract by decision, and the decision is the shape: a
screen handed the fourteen plus the team's active passage would have to work out closed from
current from future itself, which is a second place deciding where a team stands. The two
would agree on the ordinary case and disagree on the ones that matter — a passage closed out
of order, a team at the end of the book.

Two of these carry the slice.

**`test_nothing_in_this_family_writes`** is the restriction no other case catches, because a
stray write leaves every screen looking correct. D-03 puts progression on the server and the
team walks the book on its own; the facilitator reads.

**`test_a_team_that_finished_the_book_has_no_current_passage`** is ENG-469's criterion, and it
is the reason `resolve` answers `None` rather than holding the last passage.
"""

from __future__ import annotations

import itertools

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import CoverageStatus
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

TEAM_NOT_FOUND = "Team not found"
PARTIALLY_ENGAGED = CoverageStatus.PARTIALLY_ENGAGED.value

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]
FIRST, SECOND, THIRD = CANON[0], CANON[1], CANON[2]

_codes = itertools.count()


def pericopes_url(team_id: str) -> str:
    return f"/api/facilitator/teams/{team_id}/pericopes"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.facilitator.teams import facilitator_teams_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(facilitator_teams_router, prefix="/api/facilitator/teams")
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


async def a_facilitator(db: AsyncSession, *, email="facilitadora@example.com"):
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=f"p{next(_codes):02d}")
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    return user, project, await auth_header(db, user)


async def having_closed(db: AsyncSession, team, *passages: str) -> None:
    for passage in passages:
        session = await room.create_session(db, pericope=passage, project_id=team.id)
        await room.apply_coverage(
            db, session.id, dict.fromkeys(element_keys(passage), PARTIALLY_ENGAGED)
        )


def positions(body: list[dict]) -> dict[str, str]:
    return {entry["pericope"]: entry["position"] for entry in body}


# --------------------------------------------------------------- the book, in the canon's order


@pytest.mark.asyncio
async def test_the_whole_book_is_served_in_the_canons_order(client, db_session) -> None:
    _user, team, headers = await a_facilitator(db_session, email="ordem@x.com")

    body = (await client.get(pericopes_url(team.id), headers=headers)).json()

    assert [entry["pericope"] for entry in body] == CANON


@pytest.mark.asyncio
async def test_each_passage_carries_both_of_the_names_the_desk_draws(client, db_session) -> None:
    """The reference and the title, off the canon rather than composed by a screen."""
    _user, team, headers = await a_facilitator(db_session, email="nomes@x.com")

    first = (await client.get(pericopes_url(team.id), headers=headers)).json()[0]

    # Spelled with the escape because the canon writes an en dash here and a hyphen in a
    # test file is invisible.
    assert first["reference"] == "Ruth 1:1\u20135"
    assert first["title"]


@pytest.mark.asyncio
async def test_a_team_that_has_not_started_stands_on_the_first_and_the_rest_are_future(
    client, db_session
) -> None:
    _user, team, headers = await a_facilitator(db_session, email="comecando@x.com")

    where = positions((await client.get(pericopes_url(team.id), headers=headers)).json())

    assert where[FIRST] == "current"
    assert set(where.values()) == {"current", "future"}


@pytest.mark.asyncio
async def test_a_closed_passage_reads_closed_and_the_next_one_current(client, db_session) -> None:
    _user, team, headers = await a_facilitator(db_session, email="andou@x.com")
    await having_closed(db_session, team, FIRST)

    where = positions((await client.get(pericopes_url(team.id), headers=headers)).json())

    assert (where[FIRST], where[SECOND], where[THIRD]) == ("closed", "current", "future")


@pytest.mark.asyncio
async def test_a_passage_closed_out_of_order_reads_closed_and_does_not_move_the_team(
    client, db_session
) -> None:
    """The case a screen deriving positions from the active passage alone would get wrong."""
    _user, team, headers = await a_facilitator(db_session, email="fora-de-ordem@x.com")
    await having_closed(db_session, team, FIRST, THIRD)

    where = positions((await client.get(pericopes_url(team.id), headers=headers)).json())

    assert (where[SECOND], where[THIRD]) == ("current", "closed")
    assert sum(1 for position in where.values() if position == "current") == 1


@pytest.mark.asyncio
async def test_a_team_that_finished_the_book_has_no_current_passage(client, db_session) -> None:
    """ENG-469: a complete team shows its last passage as closed, not current."""
    _user, team, headers = await a_facilitator(db_session, email="terminou@x.com")
    await having_closed(db_session, team, *CANON)

    where = positions((await client.get(pericopes_url(team.id), headers=headers)).json())

    assert set(where.values()) == {"closed"}


@pytest.mark.asyncio
async def test_the_count_the_desk_draws_is_a_position_and_not_a_measure(client, db_session) -> None:
    """*"N of 14 closed"* is countable from this answer, and it is countable by the Desk.

    This route serves no number of its own. The one count the product allows is a position in
    the book, and it is drawn from the positions themselves rather than served as a total that
    could be read beside another team's.
    """
    _user, team, headers = await a_facilitator(db_session, email="contagem@x.com")
    await having_closed(db_session, team, FIRST, SECOND)

    body = (await client.get(pericopes_url(team.id), headers=headers)).json()

    assert sum(1 for entry in body if entry["position"] == "closed") == 2
    assert all(set(entry) == {"pericope", "reference", "title", "position"} for entry in body)


# ------------------------------------------------ who may read it, and the fact that nobody writes


@pytest.mark.asyncio
async def test_a_team_the_caller_does_not_facilitate_reads_as_absent(client, db_session) -> None:
    """The ENG-443 non-enumeration rule, on one more route."""
    _user, _mine, headers = await a_facilitator(db_session, email="minha@x.com")
    _other, theirs, _theirs_headers = await a_facilitator(db_session, email="deles@x.com")

    refused = await client.get(pericopes_url(theirs.id), headers=headers)
    absent = await client.get(pericopes_url("nao-existe"), headers=headers)

    assert refused.status_code == absent.status_code == 404
    assert refused.json()["detail"] == absent.json()["detail"] == TEAM_NOT_FOUND


@pytest.mark.asyncio
async def test_an_anonymous_caller_reads_nothing(client, db_session) -> None:
    _user, team, _headers = await a_facilitator(db_session, email="anon@x.com")

    assert (await client.get(pericopes_url(team.id))).status_code in (401, 403)


@pytest.mark.asyncio
async def test_nothing_in_this_family_writes(client, db_session) -> None:
    """The restriction that shapes the whole control, and the only one no screen would show.

    D-03 puts progression on the server: the team walks the book on its own and the
    facilitator reads. A route here that could move a team would leave every screen looking
    exactly right, so the absence is asserted at the door — every method other than reading is
    refused, and reading twice leaves the team where it was.
    """
    _user, team, headers = await a_facilitator(db_session, email="so-leitura@x.com")
    await having_closed(db_session, team, FIRST)

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        answer = await client.request(
            method, pericopes_url(team.id), headers=headers, json={"pericope": THIRD}
        )
        assert answer.status_code == 405, f"{method} chegou a um manipulador"

    before = positions((await client.get(pericopes_url(team.id), headers=headers)).json())
    after = positions((await client.get(pericopes_url(team.id), headers=headers)).json())

    assert before == after == {**before, SECOND: "current"}


# --------------------------------------------------------------- one source of truth, three doors


@pytest.mark.asyncio
async def test_the_three_surfaces_answer_the_same_passage(client, db_session) -> None:
    """ "One source of truth for where is this team" is the issue's own phrase, tested as one.

    Each of these was free to answer differently before the resolution existed, and two of
    them did: the work queue read the most recent session that named a passage, and the
    coverage route made the caller say. A team that skipped ahead, or worked a passage over
    two evenings, would have been drawn in three places with two answers.

    The room's own session is the fourth door and the one that matters most — it is what the
    team actually hears — so it is asserted here beside the three the Desk reads.
    """
    _user, team, headers = await a_facilitator(db_session, email="uma-verdade@x.com")
    await having_closed(db_session, team, FIRST)

    card = (await client.get("/api/facilitator/teams", headers=headers)).json()["teams"][0]
    where = positions((await client.get(pericopes_url(team.id), headers=headers)).json())
    necklace = (
        await client.get(f"/api/facilitator/teams/{team.id}/coverage", headers=headers)
    ).json()
    opened = await room.create_session(db_session, project_id=team.id)

    current = [passage for passage, position in where.items() if position == "current"]

    assert card["active_passage"]["pericope"] == SECOND
    assert current == [SECOND]
    assert [bead["key"] for bead in necklace] == element_keys(SECOND)
    assert opened.pericope == SECOND


@pytest.mark.asyncio
async def test_a_team_at_the_end_of_the_book_says_so_at_every_door(client, db_session) -> None:
    """The terminal state, agreed on rather than each door inventing its own.

    The two reads answer what they can — a card with no passage, fourteen closed — and the two
    that need a passage refuse with the same word rather than wrapping round to the first one.
    """
    from app.core.exceptions import ConflictError

    _user, team, headers = await a_facilitator(db_session, email="fim-do-livro@x.com")
    await having_closed(db_session, team, *CANON)

    card = (await client.get("/api/facilitator/teams", headers=headers)).json()["teams"][0]
    where = positions((await client.get(pericopes_url(team.id), headers=headers)).json())
    necklace = await client.get(f"/api/facilitator/teams/{team.id}/coverage", headers=headers)

    assert card["active_passage"] is None
    assert card["state"] == "complete"
    assert set(where.values()) == {"closed"}
    assert necklace.status_code == 409
    with pytest.raises(ConflictError):
        await room.create_session(db_session, project_id=team.id)
