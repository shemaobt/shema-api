"""ENG-536 — the team's own address, and the two facts only it can answer.

`GET /api/facilitator/teams/{team_id}` did not exist in any branch. The team had three
addressable panels — devices, coverage, pericopes — and no address for itself, so the Desk
built its screen by filtering the work queue.

**Cost is not why this route exists, and that was measured and discarded**: the list costs two
statements for fourteen teams and two for one, so filtering on the client costs the same. What
separates them is refusal. The three sibling panels answer **404 with an identical body** for
"not yours" and "no such team" — ENG-443's non-enumeration rule — and a client filtering a list
receives an empty list, which cannot tell those apart, nor either of them from "the filter hid
it". The screen would make four calls and three would refuse while the fourth said nothing.

Two of these carry the slice.

**`test_a_team_the_caller_does_not_facilitate_answers_exactly_as_one_that_is_absent`** is the
reason the route exists at all, so it asserts the **body** and not only the status.

**`test_the_scene_is_where_they_last_moved_and_not_where_they_have_yet_to_go`** is the only
case that separates the two readings of "the scene the team is in". Every other scenario
answers the same under both, so without it the field's meaning is decided by accident.
"""

from __future__ import annotations

import itertools

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys, elements_for
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import CoverageStatus
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    open_ir_session,
)

TEAM_NOT_FOUND = "Team not found"
PARTIALLY_ENGAGED = CoverageStatus.PARTIALLY_ENGAGED.value

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]
FIRST, SECOND, THIRD = CANON[0], CANON[1], CANON[2]

_codes = itertools.count()


def team_url(team_id: str) -> str:
    return f"/api/facilitator/teams/{team_id}"


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


async def a_facilitator(db: AsyncSession, *, email: str, tongue: str = "Terena"):
    user = await make_user(db, email=email)
    language = await make_language(db, name=tongue, code=f"d{next(_codes):02d}")
    project = await make_project(db, language.id, name=f"Equipe {email.split('@')[0]}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    return user, project, await auth_header(db, user)


async def moved(db: AsyncSession, team, *, pericope: str, keys: list[str]):
    session = await open_ir_session(db, pericope=pericope, project_id=team.id)
    await room.apply_coverage(db, session.id, dict.fromkeys(keys, PARTIALLY_ENGAGED))
    return session


async def having_closed(db: AsyncSession, team, *pericopes: str) -> None:
    for pericope in pericopes:
        await moved(db, team, pericope=pericope, keys=element_keys(pericope))


def keys_in_scene(pericope: str, scene: int | None) -> list[str]:
    return [e.key for e in elements_for(pericope) if e.scene == scene]


# ------------------------------------------------------------------ the row, at its own address


@pytest.mark.asyncio
async def test_the_team_is_served_at_its_own_address(client, db_session) -> None:
    _user, team, headers = await a_facilitator(db_session, email="propria@x.com")

    body = (await client.get(team_url(team.id), headers=headers)).json()

    assert body["team_id"] == team.id
    assert body["name"] == team.name
    assert body["mother_tongue"] == "Terena"
    assert body["active_passage"]["pericope"] == FIRST
    assert body["state"] == "in_progress"
    assert body["open_raised_hands"] == 0
    assert body["device_count"] == 0
    assert body["last_activity_at"] is None


@pytest.mark.asyncio
async def test_the_answer_carries_no_fact_about_the_facilitator(client, db_session) -> None:
    """`serves_any_team` and `open_hands_total` answer the *caller*, not this team.

    A client pulling one row out of the queue's envelope carries them along, which is the
    third reason this route exists.

    The presence is asserted before the absence, and that is not ceremony: written the other
    way round this case passed **before the route existed**, because a 404 body carries none
    of those keys either. An absence is worth what the presence beside it is worth.
    """
    _user, team, headers = await a_facilitator(db_session, email="envelope@x.com")

    body = (await client.get(team_url(team.id), headers=headers)).json()

    assert body["team_id"] == team.id
    assert "serves_any_team" not in body
    assert "open_hands_total" not in body
    assert "teams" not in body


# --------------------------------------------------------------------- the refusal, byte for byte


@pytest.mark.asyncio
async def test_a_team_the_caller_does_not_facilitate_answers_exactly_as_one_that_is_absent(
    client, db_session
) -> None:
    """The reason the route exists, so the body is asserted and not only the status.

    A client filtering the queue answers an empty list to all three of "not yours", "no such
    team" and "the filter hid it". The screen would make four calls and three would refuse.
    """
    _user, _mine, headers = await a_facilitator(db_session, email="minha@x.com")
    _other, theirs, _theirs = await a_facilitator(db_session, email="deles@x.com")

    not_yours = await client.get(team_url(theirs.id), headers=headers)
    absent = await client.get(team_url("00000000-0000-0000-0000-000000000000"), headers=headers)

    assert not_yours.status_code == absent.status_code == 404
    assert not_yours.content == absent.content
    assert not_yours.json()["detail"] == TEAM_NOT_FOUND


@pytest.mark.asyncio
async def test_an_anonymous_caller_reads_nothing(client, db_session) -> None:
    _user, team, _headers = await a_facilitator(db_session, email="anon@x.com")

    assert (await client.get(team_url(team.id))).status_code in (401, 403)


@pytest.mark.asyncio
async def test_nothing_at_this_address_writes(client, db_session) -> None:
    """D-03 again: the team walks the book on its own and the facilitator reads."""
    _user, team, headers = await a_facilitator(db_session, email="so-leitura@x.com")

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        answer = await client.request(
            method, team_url(team.id), headers=headers, json={"active_passage": THIRD}
        )
        assert answer.status_code == 405, f"{method} chegou a um manipulador"


# ------------------------------------------------------- closed_total: a position, not a measure


@pytest.mark.asyncio
async def test_a_team_that_has_not_started_has_closed_nothing(client, db_session) -> None:
    _user, team, headers = await a_facilitator(db_session, email="zero@x.com")

    assert (await client.get(team_url(team.id), headers=headers)).json()["closed_total"] == 0


@pytest.mark.asyncio
async def test_closed_total_counts_the_passages_whose_floor_is_met(client, db_session) -> None:
    _user, team, headers = await a_facilitator(db_session, email="duas@x.com")
    await having_closed(db_session, team, FIRST, SECOND)

    assert (await client.get(team_url(team.id), headers=headers)).json()["closed_total"] == 2


@pytest.mark.asyncio
async def test_a_passage_merely_touched_is_not_a_passage_closed(client, db_session) -> None:
    """`closed_total` asks the floor, and does not count the passages that have events.

    Every other case here closes whatever it touches, so a count of touched passages answers
    the same and the field's meaning would be settled by accident — measured: replacing the
    floor with `len(reached)` passed the whole file until this case existed.

    It is the same shape as the defect ENG-450 was built to refuse: counting where the
    question is whether the floor is met carries a team off work they never finished.
    """
    _user, team, headers = await a_facilitator(db_session, email="tocada@x.com")
    await having_closed(db_session, team, FIRST)
    await moved(db_session, team, pericope=SECOND, keys=element_keys(SECOND)[:3])

    body = (await client.get(team_url(team.id), headers=headers)).json()

    assert body["closed_total"] == 1
    assert body["active_passage"]["pericope"] == SECOND


@pytest.mark.asyncio
async def test_a_passage_closed_out_of_order_still_counts(client, db_session) -> None:
    """`closed_total` is about the book's passages, not about how far the team walked.

    A team on P02 with P03 already finished has closed two — and is still standing on P02.
    """
    _user, team, headers = await a_facilitator(db_session, email="fora-de-ordem@x.com")
    await having_closed(db_session, team, FIRST, THIRD)

    body = (await client.get(team_url(team.id), headers=headers)).json()

    assert body["closed_total"] == 2
    assert body["active_passage"]["pericope"] == SECOND


@pytest.mark.asyncio
async def test_a_team_that_finished_the_book_has_closed_all_of_it(client, db_session) -> None:
    _user, team, headers = await a_facilitator(db_session, email="fim@x.com")
    await having_closed(db_session, team, *CANON)

    body = (await client.get(team_url(team.id), headers=headers)).json()

    assert body["closed_total"] == len(CANON)
    assert body["active_passage"] is None
    assert body["state"] == "complete"


# ------------------------ scene_the_team_is_in: where they are, not where they owe


@pytest.mark.asyncio
async def test_the_scene_is_where_they_last_moved_and_not_where_they_have_yet_to_go(
    client, db_session
) -> None:
    """The only case that separates the two readings of the field.

    The team worked scene 3 most recently and still has scene 1 beads untouched. "Where they
    are" answers `scene:3`; "the first scene with work left" would answer `scene:1`. Every
    other scenario here answers the same under both, so without this case the meaning of the
    field would be settled by accident.
    """
    _user, team, headers = await a_facilitator(db_session, email="cena@x.com")
    scene_one = keys_in_scene(FIRST, 1)

    await moved(db_session, team, pericope=FIRST, keys=scene_one[:2])
    await moved(db_session, team, pericope=FIRST, keys=keys_in_scene(FIRST, 3)[:1])

    body = (await client.get(team_url(team.id), headers=headers)).json()

    assert body["scene_the_team_is_in"] == "scene:3"
    assert len(scene_one) > 2, "o cenário precisa de conta por trabalhar na cena 1"


@pytest.mark.asyncio
async def test_the_scene_is_served_as_a_key_and_not_as_a_number(client, db_session) -> None:
    """Same decision ENG-449 just took for `ElementCoverage.scene`: the client composes nothing."""
    _user, team, headers = await a_facilitator(db_session, email="chave@x.com")
    await moved(db_session, team, pericope=FIRST, keys=keys_in_scene(FIRST, 2)[:1])

    served = (await client.get(team_url(team.id), headers=headers)).json()["scene_the_team_is_in"]

    assert served == "scene:2"
    assert served in element_keys(FIRST), "a cena servida não é uma conta desta passagem"


@pytest.mark.asyncio
async def test_a_bead_that_spans_scenes_cannot_say_which_one_they_are_in(
    client, db_session
) -> None:
    """The case every other one here walks past, because they all move a *scene* bead.

    `elements_of` dedupes entities across the passage — Naomi in three scenes is one thing for
    the team to work with, not three — so an entity's bead carries the scene it **first**
    appeared in. Five of P01's beads are like that, and `being:B3` spans scenes 1 to 4 while
    saying `1`. Reading its scene as the team's position answers `scene:1` for a team that may
    be anywhere in the passage, which is the opposite of what the field claims.

    So a bead that belongs to more than one scene does not answer, and the most recent one that
    does answers instead. Here the team moved scene 3's own bead and then Naomi: the answer
    stays `scene:3`, because Naomi cannot say and scene 3 can.
    """
    _user, team, headers = await a_facilitator(db_session, email="abrange@x.com")

    await moved(db_session, team, pericope=FIRST, keys=keys_in_scene(FIRST, 3)[:1])
    await moved(db_session, team, pericope=FIRST, keys=["being:B3"])

    body = (await client.get(team_url(team.id), headers=headers)).json()

    assert body["scene_the_team_is_in"] == "scene:3"


@pytest.mark.asyncio
async def test_a_team_whose_only_movement_spans_scenes_is_in_no_scene(client, db_session) -> None:
    """`None` rather than the first appearance, which would be a confident wrong answer."""
    _user, team, headers = await a_facilitator(db_session, email="so-abrange@x.com")

    await moved(db_session, team, pericope=FIRST, keys=["being:B3"])

    assert (await client.get(team_url(team.id), headers=headers)).json()[
        "scene_the_team_is_in"
    ] is None


@pytest.mark.asyncio
async def test_a_team_that_has_moved_nothing_is_in_no_scene(client, db_session) -> None:
    _user, team, headers = await a_facilitator(db_session, email="parada@x.com")

    assert (await client.get(team_url(team.id), headers=headers)).json()[
        "scene_the_team_is_in"
    ] is None


@pytest.mark.asyncio
async def test_a_team_at_the_end_of_the_book_is_in_no_scene(client, db_session) -> None:
    """There is no passage they are on, so there is no scene within it."""
    _user, team, headers = await a_facilitator(db_session, email="fim-cena@x.com")
    await having_closed(db_session, team, *CANON)

    assert (await client.get(team_url(team.id), headers=headers)).json()[
        "scene_the_team_is_in"
    ] is None


@pytest.mark.asyncio
async def test_a_preservation_rule_does_not_move_them_out_of_the_scene_they_were_in(
    client, db_session
) -> None:
    """One rule for every bead that cannot locate them: it is skipped, not answered with.

    A preservation rule belongs to the passage and to none of its scenes, so it does not say
    where the team is — and neither does an entity the canon deduped across scenes. Both are
    the same refusal, so both fall through to the most recent bead that *can* say.

    This case asserted `None` before, on the reasoning that naming an earlier scene would put
    the team somewhere they had left. Held against the other rule that reasoning does not
    survive: the alternative is a panel that blanks out and comes back every time the team
    touches a rule, and `scene:1` is not a guess — it is the last place they were locatable,
    which is the honest answer to where they are.
    """
    _user, team, headers = await a_facilitator(db_session, email="preservacao@x.com")
    await moved(db_session, team, pericope=FIRST, keys=keys_in_scene(FIRST, 1)[:1])
    await moved(db_session, team, pericope=FIRST, keys=keys_in_scene(FIRST, None)[:1])

    assert (await client.get(team_url(team.id), headers=headers)).json()[
        "scene_the_team_is_in"
    ] == "scene:1"


@pytest.mark.asyncio
async def test_a_team_that_has_only_worked_the_rules_is_in_no_scene(client, db_session) -> None:
    """`None` survives where it is the whole truth: nothing they moved locates them."""
    _user, team, headers = await a_facilitator(db_session, email="so-regras@x.com")
    await moved(db_session, team, pericope=FIRST, keys=keys_in_scene(FIRST, None)[:2])

    assert (await client.get(team_url(team.id), headers=headers)).json()[
        "scene_the_team_is_in"
    ] is None


# --------------------------------------------------------------------------------- what it costs


@pytest.mark.asyncio
async def test_the_answer_does_not_pay_per_bead_or_per_team(
    client, db_session, test_engine
) -> None:
    """No N+1 in either direction: not per bead of the necklace, not per team in the roll."""
    from sqlalchemy import event

    _user, team, headers = await a_facilitator(db_session, email="custo@x.com")
    await having_closed(db_session, team, FIRST, SECOND)
    for other in range(6):
        await a_facilitator(db_session, email=f"outra{other}@x.com")

    assert (await client.get(team_url(team.id), headers=headers)).status_code == 200

    seen: list[str] = []

    @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
    def _rec(conn, cursor, statement, parameters, context, executemany):
        seen.append(" ".join(statement.split()))

    try:
        assert (await client.get(team_url(team.id), headers=headers)).status_code == 200
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _rec)

    against_events = [s for s in seen if "ir_coverage_events" in s]

    assert len(against_events) <= 2, f"mais de duas leituras dos eventos: {against_events}"
    assert len(seen) <= 4, f"a resposta custou {len(seen)} statements: {seen}"
