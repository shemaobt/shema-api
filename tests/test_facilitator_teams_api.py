"""ENG-446 — the facilitator's work queue, and the two different ways it can be empty.

The route answers two kinds of fact at once and they must not be confused. `teams` is a
fact about the **query**: what survived the search and the filter. `serves_any_team` and
`open_hands_total` are facts about the **facilitator**, and they do not narrow with the
restriction — a facilitator who left a search in the box would otherwise be told about a
fraction of their own queue and believe it.

Two cases carry the slice. `test_a_restriction_that_matches_nothing_...` is the one the
Desk cannot survive without: an empty array means "clear your search" in one case and
"talk to administration" in the other, and those ask opposite things of the person
reading the screen.

`test_the_number_of_statements_does_not_grow_with_the_teams` asserts the acceptance
criterion about N+1 by comparing two runs rather than by counting to a number. The number
includes whatever the door itself asks, which is not this route's business and would make
the case fail for a reason it is not about.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import (
    IRQuestion,
    IRQuestionStatus,
    IRSession,
    IRSessionStatus,
)
from app.services.device.create_device import create_device
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import apply_coverage, create_session
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    open_ir_session,
)

TEAMS_URL = "/api/facilitator/teams"

#: Far enough past any threshold this route could reasonably hold, so the case says
#: "long ago" rather than restating the constant it is measuring.
LONG_AGO = timedelta(days=90)
RECENTLY = timedelta(days=2)


def team_devices_url(team_id: str) -> str:
    return f"{TEAMS_URL}/{team_id}/devices"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.facilitator.teams import facilitator_teams_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(facilitator_teams_router, prefix=TEAMS_URL)
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


#: `languages.code` is a unique `String(3)`, so the codes have to differ — but only within
#: one test, since the schema is rebuilt for each. Wrapping at a hundred is therefore safe,
#: and it is written that way so that adding the hundred-and-first team does not silently
#: collide with the first.
_made = 0


async def a_team(db: AsyncSession, *, name: str, tongue: str | None = None):
    """A project, which is what a team is (D-16), with a language of its own."""
    global _made
    _made += 1
    language = await make_language(db, name=tongue or name, code=f"t{_made % 100:02d}")
    return await make_project(db, language.id, name=name)


async def a_facilitator(db: AsyncSession, *teams, email: str = "facilitadora@example.com"):
    user = await make_user(db, email=email)
    for team in teams:
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    return user, await auth_header(db, user)


async def a_session(
    db: AsyncSession,
    team,
    *,
    pericope: str = "P01",
    status: IRSessionStatus = IRSessionStatus.IN_PROGRESS,
    when: datetime | None = None,
) -> IRSession:
    at = when or datetime.now(UTC) - RECENTLY
    session = IRSession(
        pericope=pericope,
        status=status,
        project_id=team.id,
        messages=[],
        coverage_state={},
        kept_takes={},
        back_translation={},
        created_at=at,
        updated_at=at,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def having_closed(db: AsyncSession, team, *passages: str) -> None:
    """Walk this team through these passages the way the room does.

    The coverage events — what these routes actually read — are still written by
    `apply_coverage`, so the fixture cannot agree with a route that reads them differently
    from how the room writes them. `open_ir_session` says what it inserts and when.
    """
    for passage in passages:
        session = await open_ir_session(db, pericope=passage, project_id=team.id)
        await apply_coverage(
            db,
            session.id,
            dict.fromkeys(element_keys(passage), CoverageStatus.PARTIALLY_ENGAGED.value),
        )


async def having_closed_the_book(db: AsyncSession, team) -> None:
    """Walk this team to the end of Ruth.

    The events are written by `apply_coverage` rather than inserted, so a fixture cannot agree
    with a resolution that reads them differently from how the room writes them. It is fourteen
    passages because "complete" now means the book, not a session — and since ENG-589 eight of
    them are no longer passages the room will open, which is what `open_ir_session` covers.
    """
    from app.services.internalization_room import sessions as room
    from app.services.internalization_room.canon.elements import element_keys
    from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
    from app.services.internalization_room.coverage import CoverageStatus

    for meaning_map in load_book(ROOM_BOOK):
        passage = meaning_map.pericope_num
        session = await open_ir_session(db, pericope=passage, project_id=team.id)
        await room.apply_coverage(
            db,
            session.id,
            dict.fromkeys(element_keys(passage), CoverageStatus.PARTIALLY_ENGAGED.value),
        )


async def a_raised_hand(
    db: AsyncSession,
    team,
    *,
    status: IRQuestionStatus = IRQuestionStatus.OPEN,
    when: datetime | None = None,
) -> IRQuestion:
    question = IRQuestion(
        device_id="aparelho",
        session_id="sessao",
        pericope="P01",
        audio_key="pergunta.m4a",
        status=status,
        project_id=team.id,
        created_at=when or datetime.now(UTC) - RECENTLY,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


async def a_device(db: AsyncSession, team, *, unlinked: bool = False):
    minted = await create_device(db)
    minted.device.project_id = team.id
    minted.device.claimed_at = datetime.now(UTC)
    if unlinked:
        minted.device.unlinked_at = datetime.now(UTC)
    await db.commit()
    return minted.device


def named(payload: dict) -> list[str]:
    return [team["name"] for team in payload["teams"]]


# Behaviour 1 — the list is the caller's, and it carries the whole card.


@pytest.mark.asyncio
async def test_the_list_holds_only_the_teams_the_caller_facilitates(client, db_session):
    mine = await a_team(db_session, name="Equipe Terena")
    await a_team(db_session, name="Equipe de Outra Pessoa")
    _user, headers = await a_facilitator(db_session, mine)

    answer = await client.get(TEAMS_URL, headers=headers)

    assert answer.status_code == 200
    assert named(answer.json()) == ["Equipe Terena"]


@pytest.mark.asyncio
async def test_every_field_the_card_draws_is_answered(client, db_session):
    """The client computes none of them — so each has to arrive, not be derivable."""
    team = await a_team(db_session, name="Equipe Terena", tongue="Terena")
    await a_session(db_session, team, pericope="P01")
    await a_raised_hand(db_session, team)
    await a_device(db_session, team)
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["team_id"] == team.id
    assert card["name"] == "Equipe Terena"
    assert card["mother_tongue"] == "Terena"
    assert card["active_passage"]["pericope"] == "P01"
    # Spelled with the escape because the canon writes an en dash here and a hyphen in a
    # test file is invisible. What the facilitator types is a hyphen — see the search case.
    assert card["active_passage"]["reference"] == "Ruth 1:1\u20135"
    assert card["state"] == "in_progress"
    assert card["open_raised_hands"] == 1
    assert card["device_count"] == 1
    assert card["last_activity_at"] is not None


@pytest.mark.asyncio
async def test_a_team_that_has_never_held_a_session_still_has_a_passage(client, db_session):
    """§4: with no history the team starts at P01. A card with no passage draws nothing."""
    team = await a_team(db_session, name="Equipe Guajajara")
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["active_passage"]["pericope"] == "P01"
    assert card["last_activity_at"] is None


@pytest.mark.asyncio
async def test_the_panorama_is_not_a_passage(client, db_session):
    """The panorama is material about the book and plays at the opening of a new passage.

    A team whose most recent session is the panorama is not working on `OV-Ruth` — there is no
    such passage, and the canon refuses to be asked for one.

    This used to be a filter on the query that picked the latest session. Since ENG-450 the
    card's passage comes from walking the canon's own fourteen, which `OV-Ruth` is not one of,
    so the answer cannot name it however recent that session is. The case stays because the
    property is worth pinning; what changed is that nothing has to remember to exclude it.
    """
    team = await a_team(db_session, name="Equipe Munduruku")
    await a_session(db_session, team, pericope="P02", when=datetime.now(UTC) - timedelta(days=3))
    await a_session(db_session, team, pericope="OV-Ruth")
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["active_passage"]["pericope"] == "P01"


# Behaviour 2 — the counts are of things to do, and they agree with the routes that own them.


@pytest.mark.asyncio
async def test_only_an_open_hand_is_a_hand_that_is_waiting(client, db_session):
    team = await a_team(db_session, name="Equipe Terena")
    await a_raised_hand(db_session, team, status=IRQuestionStatus.OPEN)
    await a_raised_hand(db_session, team, status=IRQuestionStatus.ANSWERED)
    await a_raised_hand(db_session, team, status=IRQuestionStatus.RESOLVED)
    _user, headers = await a_facilitator(db_session, team)

    payload = (await client.get(TEAMS_URL, headers=headers)).json()

    assert payload["teams"][0]["open_raised_hands"] == 1
    assert payload["open_hands_total"] == 1


@pytest.mark.asyncio
async def test_the_device_count_agrees_with_the_device_list_route(client, db_session):
    """One number, two routes. They are allowed to be wrong; they are not allowed to differ."""
    team = await a_team(db_session, name="Equipe Terena")
    await a_device(db_session, team)
    await a_device(db_session, team)
    await a_device(db_session, team, unlinked=True)
    _user, headers = await a_facilitator(db_session, team)

    counted = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]["device_count"]
    listed = (await client.get(team_devices_url(team.id), headers=headers)).json()

    assert counted == len(listed) == 2


@pytest.mark.asyncio
async def test_a_hand_belonging_to_no_team_is_counted_for_nobody(client, db_session):
    """`project_id` is nullable and null is the normal state until ENG-454 ships.

    A row that names no team cannot be attributed to one, and attributing it to all of
    them would put work on a facilitator's queue that is not theirs.
    """
    team = await a_team(db_session, name="Equipe Terena")
    orphan = IRQuestion(
        device_id="aparelho-sem-equipe",
        session_id="sessao",
        pericope="P01",
        audio_key="pergunta.m4a",
        status=IRQuestionStatus.OPEN,
        project_id=None,
    )
    db_session.add(orphan)
    await db_session.commit()
    _user, headers = await a_facilitator(db_session, team)

    payload = (await client.get(TEAMS_URL, headers=headers)).json()

    assert payload["teams"][0]["open_raised_hands"] == 0
    assert payload["open_hands_total"] == 0


# Behaviour 3 — the state, defined here once and served.


@pytest.mark.asyncio
async def test_a_team_that_closed_every_passage_reads_complete_and_stands_on_none(
    client, db_session
):
    """`complete` used to mean the latest session was done, which is now a passing moment.

    Since ENG-450 a closed passage moves the team to the next one, so the only way to have
    nothing left is to have reached the end of the book — and there `active_passage` is null,
    which is what lets the Desk draw the last passage closed rather than current.
    """
    team = await a_team(db_session, name="Equipe Tikuna")
    await having_closed_the_book(db_session, team)
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["state"] == "complete"
    assert card["active_passage"] is None


@pytest.mark.asyncio
async def test_closing_one_passage_moves_the_team_on_rather_than_finishing_it(client, db_session):
    """The case that separates the two meanings of "done" the old state collapsed."""
    team = await a_team(db_session, name="Equipe Kayapó")
    session = await create_session(db_session, pericope="P01", project_id=team.id)
    await apply_coverage(
        db_session,
        session.id,
        dict.fromkeys(element_keys("P01"), CoverageStatus.PARTIALLY_ENGAGED.value),
    )
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["active_passage"]["pericope"] == "P02"
    assert card["state"] == "in_progress"


@pytest.mark.asyncio
async def test_a_team_that_finished_the_book_is_still_found_by_name(client, db_session):
    """The search reads the passage's two names, and such a team has neither.

    Without this the search raises on the one team it is most reasonable to look up by name.
    """
    team = await a_team(db_session, name="Equipe Tikuna")
    await having_closed_the_book(db_session, team)
    _user, headers = await a_facilitator(db_session, team)

    answer = await client.get(TEAMS_URL, params={"search": "tikuna"}, headers=headers)

    assert named(answer.json()) == ["Equipe Tikuna"]


@pytest.mark.asyncio
async def test_a_passage_left_untouched_for_long_enough_reads_stalled(client, db_session):
    team = await a_team(db_session, name="Equipe Xavante")
    await a_session(db_session, team, when=datetime.now(UTC) - LONG_AGO)
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["state"] == "stalled"


@pytest.mark.asyncio
async def test_a_finished_passage_is_never_stalled_however_long_ago_it_was(client, db_session):
    """Stalled means work has stopped, not that the team is quiet. A team that finished
    and moved on is not somebody to chase."""
    team = await a_team(db_session, name="Equipe Apurinã")
    await having_closed_the_book(db_session, team)
    for session in (await db_session.execute(select(IRSession))).scalars():
        session.updated_at = datetime.now(UTC) - LONG_AGO
    await db_session.commit()
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["state"] == "complete"


@pytest.mark.asyncio
async def test_a_team_that_has_never_met_is_in_progress_and_not_stalled(client, db_session):
    """ "Never started" is not "stopped".

    A team waiting for its first session would otherwise arrive at the top of the list as
    somebody to chase, and there is nothing to chase them about.
    """
    team = await a_team(db_session, name="Equipe Guajajara")
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["state"] == "in_progress"


@pytest.mark.asyncio
async def test_a_hand_raised_since_keeps_a_team_out_of_stalled(client, db_session):
    """A raised hand is the team doing something, and it is not in the session's row."""
    team = await a_team(db_session, name="Equipe Macuxi")
    await a_session(db_session, team, when=datetime.now(UTC) - LONG_AGO)
    await a_raised_hand(db_session, team)
    _user, headers = await a_facilitator(db_session, team)

    card = (await client.get(TEAMS_URL, headers=headers)).json()["teams"][0]

    assert card["state"] == "in_progress"


# Behaviour 4 — the order is the product decision, so it is served.


@pytest.mark.asyncio
async def test_the_queue_is_ordered_by_open_hands_then_by_recent_activity(client, db_session):
    quiet = await a_team(db_session, name="Silenciosa")
    busy = await a_team(db_session, name="Duas maos")
    recent = await a_team(db_session, name="Uma mao recente")
    older = await a_team(db_session, name="Uma mao antiga")

    await a_raised_hand(db_session, busy)
    await a_raised_hand(db_session, busy)
    await a_raised_hand(db_session, recent, when=datetime.now(UTC) - timedelta(days=1))
    await a_raised_hand(db_session, older, when=datetime.now(UTC) - timedelta(days=10))
    await a_session(db_session, quiet)

    _user, headers = await a_facilitator(db_session, quiet, busy, recent, older)

    assert named((await client.get(TEAMS_URL, headers=headers)).json()) == [
        "Duas maos",
        "Uma mao recente",
        "Uma mao antiga",
        "Silenciosa",
    ]


@pytest.mark.asyncio
async def test_a_team_that_has_never_acted_sorts_last_rather_than_first(client, db_session):
    never = await a_team(db_session, name="Nunca se reuniu")
    long_quiet = await a_team(db_session, name="Calada ha muito")
    await a_session(db_session, long_quiet, when=datetime.now(UTC) - LONG_AGO)
    _user, headers = await a_facilitator(db_session, never, long_quiet)

    assert named((await client.get(TEAMS_URL, headers=headers)).json()) == [
        "Calada ha muito",
        "Nunca se reuniu",
    ]


# Behaviour 5 — the two empty states are different things and are told apart.


@pytest.mark.asyncio
async def test_a_facilitator_with_no_teams_gets_an_empty_list_and_says_so(client, db_session):
    user = await make_user(db_session, email="sem-equipe@example.com")
    await grant_facilitator_app_role(db_session, user.id)
    headers = await auth_header(db_session, user)

    answer = await client.get(TEAMS_URL, headers=headers)

    assert answer.status_code == 200
    assert answer.json() == {"teams": [], "serves_any_team": False, "open_hands_total": 0}


@pytest.mark.asyncio
async def test_a_restriction_that_matches_nothing_still_says_the_facilitator_has_teams(
    client, db_session
):
    """The case the Desk cannot survive without.

    Both answers carry an empty array, and they ask opposite things of the facilitator:
    clear the search, or talk to administration. Nothing in the array itself tells them
    apart, and a screen that remembered which it was would be holding state that goes
    stale the moment a search empties the list.
    """
    team = await a_team(db_session, name="Equipe Terena")
    _user, headers = await a_facilitator(db_session, team)

    nothing_matched = await client.get(TEAMS_URL, params={"search": "Xavante"}, headers=headers)

    assert nothing_matched.status_code == 200
    assert nothing_matched.json()["teams"] == []
    assert nothing_matched.json()["serves_any_team"] is True


# Behaviour 6 — the restriction is the server's, and the totals do not travel with it.


@pytest.mark.asyncio
async def test_the_search_ignores_case_and_accents(client, db_session):
    """Somebody typing at speed does not stop for an accent, and the keyboard may not
    carry one. The shape of the word belongs to whoever wrote it down."""
    team = await a_team(db_session, name="Equipe Kaiwá", tongue="Kaiwá")
    _user, headers = await a_facilitator(db_session, team)

    for typed in ("Kaiwa", "kaiwa", "KAIWÁ", "kaiwá"):
        found = await client.get(TEAMS_URL, params={"search": typed}, headers=headers)
        assert named(found.json()) == ["Equipe Kaiwá"], typed


@pytest.mark.asyncio
async def test_the_search_reaches_the_tongue_the_pericope_and_the_reference(client, db_session):
    """The card draws all of them, so any of them is what the facilitator remembers."""
    team = await a_team(db_session, name="Equipe Sateré-Mawé", tongue="Sateré-Mawé")
    # Walked to P03 rather than given a session on it: the card's passage is resolved from
    # what the team finished, so a session naming P03 with nothing closed before it leaves the
    # team on P01 — and the case would fail on its fixture rather than on its subject.
    await having_closed(db_session, team, "P01", "P02")
    _user, headers = await a_facilitator(db_session, team)

    for typed in ("satere", "P03", "Ruth 1:15", "1:15-18"):
        found = await client.get(TEAMS_URL, params={"search": typed}, headers=headers)
        assert named(found.json()) == ["Equipe Sateré-Mawé"], typed


@pytest.mark.asyncio
async def test_each_filter_narrows_to_the_state_it_names(client, db_session):
    with_hands = await a_team(db_session, name="Com maos")
    working = await a_team(db_session, name="Trabalhando")
    stopped = await a_team(db_session, name="Parada")
    finished = await a_team(db_session, name="Concluida")

    await a_raised_hand(db_session, with_hands)
    await a_session(db_session, with_hands)
    await a_session(db_session, working)
    await a_session(db_session, stopped, when=datetime.now(UTC) - LONG_AGO)
    await having_closed_the_book(db_session, finished)

    _user, headers = await a_facilitator(db_session, with_hands, working, stopped, finished)

    async def under(filter_name: str) -> list[str]:
        answer = await client.get(TEAMS_URL, params={"filter": filter_name}, headers=headers)
        return sorted(named(answer.json()))

    assert await under("all") == ["Com maos", "Concluida", "Parada", "Trabalhando"]
    assert await under("with_hands") == ["Com maos"]
    assert await under("in_progress") == ["Com maos", "Trabalhando"]
    assert await under("stalled") == ["Parada"]
    assert await under("complete") == ["Concluida"]


@pytest.mark.asyncio
async def test_the_search_and_the_filter_compose(client, db_session):
    """One question, not two answers for the screen to intersect."""
    quiet_kaiwa = await a_team(db_session, name="Equipe Kaiwá", tongue="Kaiwá")
    busy_kaiwa = await a_team(db_session, name="Equipe Kaiwá do rio", tongue="Kaiwá")
    busy_other = await a_team(db_session, name="Equipe Terena")

    await a_raised_hand(db_session, busy_kaiwa)
    await a_raised_hand(db_session, busy_other)

    _user, headers = await a_facilitator(db_session, quiet_kaiwa, busy_kaiwa, busy_other)

    answer = await client.get(
        TEAMS_URL, params={"search": "kaiwa", "filter": "with_hands"}, headers=headers
    )

    assert named(answer.json()) == ["Equipe Kaiwá do rio"]


@pytest.mark.asyncio
async def test_the_open_hands_total_does_not_narrow_with_the_restriction(client, db_session):
    """The browser tab draws this number while nobody is looking at the Desk.

    A facilitator who left a search typed in the box would be told about a fraction of
    their queue and would believe it, because the tab shows no search.
    """
    searched = await a_team(db_session, name="Equipe Terena")
    other = await a_team(db_session, name="Equipe Xavante")
    await a_raised_hand(db_session, searched)
    await a_raised_hand(db_session, other)
    await a_raised_hand(db_session, other)
    _user, headers = await a_facilitator(db_session, searched, other)

    narrowed = (await client.get(TEAMS_URL, params={"search": "Terena"}, headers=headers)).json()

    assert named(narrowed) == ["Equipe Terena"]
    assert narrowed["teams"][0]["open_raised_hands"] == 1
    assert narrowed["open_hands_total"] == 3


@pytest.mark.asyncio
async def test_a_filter_this_route_does_not_know_is_refused(client, db_session):
    team = await a_team(db_session, name="Equipe Terena")
    _user, headers = await a_facilitator(db_session, team)

    answer = await client.get(TEAMS_URL, params={"filter": "com-problema"}, headers=headers)

    assert answer.status_code == 422


# Behaviour 7 — one query, whatever the size of the roll.


@pytest.mark.asyncio
async def test_the_number_of_statements_does_not_grow_with_the_teams(
    client, db_session, test_engine
):
    """The acceptance criterion, asserted as the property it actually is.

    Counting to a fixed number would be counting the door's own lookups too, which is not
    this route's business and would redden this case for a reason it is not about. Two
    rolls of different sizes costing the same is what "no N+1 over teams" means.

    Both measurements are taken with the door's caches already warm. Measured across that
    boundary the first request costs more than the second, which reads as the queue getting
    *cheaper* as it grows — a green that would mean nothing.
    """
    statements: list[str] = []

    @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        small = [await a_team(db_session, name=f"Equipe {n}") for n in range(2)]
        _user, headers = await a_facilitator(db_session, *small)
        await client.get(TEAMS_URL, headers=headers)
        statements.clear()
        assert (await client.get(TEAMS_URL, headers=headers)).status_code == 200
        for_two = len(statements)

        large = [await a_team(db_session, name=f"Equipe grande {n}") for n in range(12)]
        for team in large:
            await make_project_user_access(db_session, team.id, _user.id, role="facilitator")
            await a_session(db_session, team)
            await a_raised_hand(db_session, team)
            await a_device(db_session, team)
        statements.clear()
        assert (await client.get(TEAMS_URL, headers=headers)).status_code == 200
        for_fourteen = len(statements)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _count)

    assert for_two == for_fourteen, (
        f"duas equipes custaram {for_two} instrucoes e catorze custaram {for_fourteen}: "
        "a consulta cresce com a lista"
    )


# Behaviour 8 — a platform admin is not scoped to nothing.


@pytest.mark.asyncio
async def test_a_platform_admin_sees_every_team(client, db_session):
    """Settled by ENG-439 and repeated here rather than assumed: the one person able to
    investigate an installation must not be the one person who sees no team in it."""
    await a_team(db_session, name="Primeira")
    await a_team(db_session, name="Segunda")
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    payload = (await client.get(TEAMS_URL, headers=headers)).json()

    assert sorted(named(payload)) == ["Primeira", "Segunda"]
    assert payload["serves_any_team"] is True
