"""ENG-451 — the passage's history: the live conversation first, then newest to oldest.

Four of these carry the slice.

**The order was measured wrong and is fixed here.** Start time alone put a conversation still
going on the 12th under a finished one from the 19th — the one session a facilitator can act
on, buried under one they cannot. Two of the three ordering tests were red before the fix.

**Nothing ends a session for being idle (ENG-1263).** A conversation left for thirty days
reads `in_progress`, leads the history while it is the live one, and keeps its halt.

**The project scoping is measured, not inherited.** Every session in the field today has a
null project — the room app does not send its device credential until ENG-454 — so a route
that returned them would look perfectly right on a working installation and would hand every
facilitator every other team's history. A number that is right by accident reads exactly
like a number that is right by construction, so the null case is asserted rather than
assumed.

**The end is the moment the floor was met.** A session that never met it has no end and no
length, however long nobody asks.

**Every timestamp on the wire carries its offset.** ``DateTime(timezone=True)`` is naive on
SQLite and aware on Postgres, and a bare ``20:00:56`` was measured coming off the device
route this week — on a UTC-3 machine that is three hours of error, in a column a facilitator
reads as the day the conversation happened.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus
from tests.baker import (
    grant_facilitator_app_role,
    keep_a_take,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

P = "P03"
SURFACED = CoverageStatus.SURFACED.value
ENGAGED = CoverageStatus.ENGAGED.value
NOT_ENCOUNTERED = CoverageStatus.NOT_ENCOUNTERED.value

TEAM_NOT_FOUND = "Team not found"


def sessions_url(team_id: str) -> str:
    return f"/api/facilitator/teams/{team_id}/sessions"


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


async def a_facilitator(db: AsyncSession, *, email="facilitator@example.com"):
    """Someone who facilitates this team **and** holds the room's facilitator role.

    Two different things since ENG-438, and both are needed to reach the handler: the app
    role opens the door and the project access decides which teams are theirs. That the door
    refuses everyone else is `test_facilitator_role_gate.py`'s subject, and this route is in
    its table.
    """
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    return user, project, await auth_header(db, user)


async def a_session(
    db: AsyncSession,
    *,
    project_id: str | None,
    pericope: str = P,
    opened_at: datetime | None = None,
    updated_at: datetime | None = None,
    entered: bool = True,
):
    """A conversation, optionally moved back in time so it can be an old one.

    `entered` lands one turn by default (ENG-964): every case in this file but the ones
    naming the boundary itself is about a conversation the team held, and a session with
    no turn and no take is not one. Pass `entered=False` for the cases that test that
    boundary.
    """
    session = await room.create_session(
        db,
        pericope=pericope,
        project_id=project_id,
    )
    if entered:
        session = await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")
    if opened_at is not None:
        session.created_at = opened_at
    if updated_at is not None:
        session.updated_at = updated_at
    if opened_at is not None or updated_at is not None:
        await db.commit()
        await db.refresh(session)
    return session


async def read_history(client, team_id: str, headers) -> list[dict]:
    answer = await client.get(sessions_url(team_id), headers=headers)
    assert answer.status_code == 200, answer.text
    return answer.json()


# Behaviour 1 — the history is the team's own, newest first.


async def test_the_history_reads_from_the_most_recent_conversation_backwards(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    day = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    oldest = await a_session(db_session, project_id=project.id, opened_at=day)
    newest = await a_session(db_session, project_id=project.id, opened_at=day + timedelta(days=4))
    middle = await a_session(db_session, project_id=project.id, opened_at=day + timedelta(days=2))

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [newest.id, middle.id, oldest.id]


async def test_the_conversation_still_going_leads_however_old_it_is(client, db_session):
    """The one session in the column the facilitator can still act on.

    Measured against this route as it was: a live conversation from the 12th sank under a
    finished one from the 19th. Start time alone buries the only live thing in the history,
    which is the defect ENG-487 closed on the Desk — arriving back through the server.
    """
    _user, project, headers = await a_facilitator(db_session)
    finished = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 19, 9, 0, tzinfo=UTC),
    )
    finished.ended_at = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    still_going = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
        updated_at=datetime.now(UTC),
    )
    await db_session.commit()

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [still_going.id, finished.id]
    assert history[0]["state"] == "in_progress"


async def test_a_conversation_days_old_still_leads_when_it_is_the_live_one(client, db_session):
    """Nothing ends a session for being idle, so the live one leads however long it sat."""
    _user, project, headers = await a_facilitator(db_session)
    finished = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 19, 9, 0, tzinfo=UTC),
    )
    finished.ended_at = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    quiet = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
        updated_at=datetime.now(UTC) - timedelta(days=30),
    )
    await db_session.commit()

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [quiet.id, finished.id]
    assert history[0]["state"] == "in_progress"


async def test_two_conversations_still_going_lead_in_the_order_they_opened(client, db_session):
    """Leading is a group and not a slot: within it the history still reads backwards."""
    _user, project, headers = await a_facilitator(db_session)
    finished = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 19, 9, 0, tzinfo=UTC),
    )
    finished.ended_at = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    older = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
        updated_at=datetime.now(UTC),
    )
    newer = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
        updated_at=datetime.now(UTC),
    )
    await db_session.commit()

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [newer.id, older.id, finished.id]


async def test_another_teams_conversations_are_not_in_this_teams_history(client, db_session):
    _user, mine, headers = await a_facilitator(db_session)
    _other, theirs, _ = await a_facilitator(db_session, email="other@example.com")
    ours = await a_session(db_session, project_id=mine.id)
    await a_session(db_session, project_id=theirs.id)

    history = await read_history(client, mine.id, headers)

    assert [card["session_id"] for card in history] == [ours.id]


async def test_a_conversation_that_belongs_to_no_team_is_served_to_nobody(client, db_session):
    """Every session in the field is like this until ENG-454, which is what makes it worth
    asserting: a route that leaked them would look right on every installation that has one.
    """
    _user, project, headers = await a_facilitator(db_session)
    await a_session(db_session, project_id=None)

    assert await read_history(client, project.id, headers) == []


# Behaviour 1b — a session nobody entered is not a room (ENG-964).


async def test_a_session_nobody_entered_is_not_drawn(client, db_session):
    """No turn, no take: the invitation door and the panorama spoke mint a session before
    any stored row is read (ADR 0033 of the internalization-room repository), and the
    minted one is left unentered when the stored row wins. It is not a room of the team,
    so the column answers with the live one only.
    """
    _user, project, headers = await a_facilitator(db_session)
    live = await a_session(
        db_session, project_id=project.id, opened_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    )
    await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 19, 9, 0, tzinfo=UTC),
        entered=False,
    )

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [live.id]


async def test_a_take_with_no_turn_is_still_entered(client, db_session):
    """A team that recorded and left, without a turn landing, still held the room."""
    _user, project, headers = await a_facilitator(db_session)
    session = await a_session(db_session, project_id=project.id, entered=False)
    await keep_a_take(db_session, session)

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [session.id]


async def test_a_session_left_in_the_middle_and_a_halted_one_are_still_answered(client, db_session):
    """A session with a turn is answered whether it is still open or halted — the rule is
    about being entered, not about being finished."""
    _user, project, headers = await a_facilitator(db_session)
    left_in_the_middle = await a_session(
        db_session, project_id=project.id, opened_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    )
    halted = await a_session(
        db_session, project_id=project.id, opened_at=datetime(2026, 8, 19, 9, 0, tzinfo=UTC)
    )
    await room.mark_needs_person(db_session, halted)

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [halted.id, left_in_the_middle.id]


async def test_a_session_halted_before_any_turn_landed_is_still_answered(client, db_session):
    """Calling a person is an act of the team, even the very first one: the tablet can ask
    for a person before a turn ever lands — a slow-record watchdog, or resuming a passage
    whose parts never came back — and the facilitator attends from this column.
    """
    _user, project, headers = await a_facilitator(db_session)
    halted = await a_session(db_session, project_id=project.id, entered=False)
    await room.mark_needs_person(db_session, halted)

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [halted.id]


async def test_a_halt_that_never_had_a_turn_outlives_being_attended(client, db_session):
    """`halt_kind` is written on every halt and cleared by none (`halt.last`'s own rule): a
    room a facilitator has already gone to does not drop back out of the column just because
    `attend` lifted its status — the halt it asked for is still a fact of its history.
    """
    _user, project, headers = await a_facilitator(db_session)
    halted = await a_session(db_session, project_id=project.id, entered=False)
    await room.mark_needs_person(db_session, halted)

    await room.attend(db_session, halted, by="quem-foi")

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [halted.id]
    assert history[0]["needs_person"] is False


# Behaviour 2 — a team that is not the caller's refuses exactly as one that does not exist.


async def test_a_team_the_caller_does_not_facilitate_is_refused_as_if_it_did_not_exist(
    client, db_session
):
    _user, _mine, headers = await a_facilitator(db_session)
    _other, theirs, _ = await a_facilitator(db_session, email="other@example.com")

    not_mine = await client.get(sessions_url(theirs.id), headers=headers)
    no_such_thing = await client.get(sessions_url("no-such-team"), headers=headers)

    assert not_mine.status_code == no_such_thing.status_code == 404
    assert not_mine.json() == no_such_thing.json()
    assert TEAM_NOT_FOUND in not_mine.text


# Behaviour 3 — the three states, and the length that comes with two of them.


async def test_a_conversation_still_going_has_no_end_and_no_length(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    await a_session(db_session, project_id=project.id)

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "in_progress"
    assert card["ended_at"] is None
    assert card["duration_minutes"] is None


async def test_a_conversation_closed_by_the_floor_reads_complete_with_its_length(
    client, db_session
):
    _user, project, headers = await a_facilitator(db_session)
    session = await a_session(db_session, project_id=project.id)
    session.created_at = datetime.now(UTC) - timedelta(minutes=34)
    await db_session.commit()

    await room.apply_coverage(db_session, session.id, dict.fromkeys(element_keys(P), ENGAGED))

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "complete"
    assert card["ended_at"] is not None
    assert card["duration_minutes"] == 34


@pytest.mark.parametrize("idle", [timedelta(hours=7), timedelta(days=30)])
async def test_the_desk_never_calls_a_session_abandoned_however_long_it_sat(
    client, db_session, idle
):
    _user, project, headers = await a_facilitator(db_session)
    await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime.now(UTC) - idle - timedelta(minutes=47),
        updated_at=datetime.now(UTC) - idle,
    )

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "in_progress"
    assert card["ended_at"] is None
    assert card["duration_minutes"] is None


# Behaviour 4 — every timestamp says which clock it is on.


async def test_every_moment_on_the_wire_carries_its_offset(client, db_session):
    """A bare `2026-08-20T15:00:00` is read as local by whoever receives it."""
    _user, project, headers = await a_facilitator(db_session)
    closed = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 20, 14, 13, tzinfo=UTC),
    )
    closed.ended_at = datetime(2026, 8, 20, 15, 0, tzinfo=UTC)
    await db_session.commit()

    [card] = await read_history(client, project.id, headers)

    for field in ("started_at", "ended_at"):
        assert card[field].endswith(("Z", "+00:00")), (
            f"{field} went out as {card[field]!r}, which names no clock"
        )


# Behaviour 5 — the portrait is that session's necklace and no other's.


async def test_the_portrait_is_the_necklace_as_that_session_left_it(client, db_session):
    """A later conversation's beads must not appear on an earlier conversation's card."""
    _user, project, headers = await a_facilitator(db_session)
    keys = element_keys(P)
    day = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)

    first = await a_session(db_session, project_id=project.id, opened_at=day)
    await room.apply_coverage(db_session, first.id, {keys[0]: ENGAGED})
    second = await a_session(db_session, project_id=project.id, opened_at=day + timedelta(days=1))
    await room.apply_coverage(db_session, second.id, {keys[1]: SURFACED})

    newest, oldest = await read_history(client, project.id, headers)

    assert oldest["session_id"] == first.id
    on_the_older = {bead["key"]: bead["status"] for bead in oldest["coverage"]}
    assert on_the_older[keys[0]] == ENGAGED
    assert on_the_older[keys[1]] == NOT_ENCOUNTERED, "the later conversation's bead leaked back"

    on_the_newer = {bead["key"]: bead["status"] for bead in newest["coverage"]}
    assert on_the_newer[keys[1]] == SURFACED
    assert on_the_newer[keys[0]] == ENGAGED, (
        "the first conversation's bead is missing from the second conversation's card — "
        "the portrait is that session's diff rather than the necklace as it stood"
    )
    assert set(on_the_newer) == set(keys), (
        "the portrait has to carry the whole spine, not only the beads that moved"
    )


async def test_the_beads_arrive_in_the_order_the_necklace_strings_them(client, db_session):
    """The mini necklace and the full one are one drawing; ENG-449 reads the same canon."""
    _user, project, headers = await a_facilitator(db_session)
    await a_session(db_session, project_id=project.id)

    [card] = await read_history(client, project.id, headers)

    assert [bead["key"] for bead in card["coverage"]] == element_keys(P)


async def test_a_bead_names_itself_in_every_language_the_desk_offers(client, db_session):
    """The portrait is read out bead by bead to a facilitator who does not see it."""
    _user, project, headers = await a_facilitator(db_session)
    await a_session(db_session, project_id=project.id)

    [card] = await read_history(client, project.id, headers)
    bead = card["coverage"][0]

    assert set(bead) == {"key", "kind", "label_pt", "label_en", "status"}
    assert bead["label_en"]
    assert bead["kind"] == "arc"


async def test_a_panorama_is_kept_in_the_history_with_nothing_to_draw(client, db_session):
    """`OV-Ruth` addresses the book and has no spine.

    Dropping it would hide a conversation the team really held; the Desk draws an empty
    portrait as a conversation that reached nothing, which is what happened. Unreachable
    today — every session's project is null until ENG-454 — and reachable after it.
    """
    _user, project, headers = await a_facilitator(db_session)
    await a_session(db_session, project_id=project.id, pericope="OV")

    [card] = await read_history(client, project.id, headers)

    assert card["coverage"] == []
    assert card["pericope"].startswith("OV-")


# Behaviour 6 — a team that has never met has an empty history, not a refusal.


async def test_a_team_that_has_never_met_answers_with_an_empty_history(client, db_session):
    _user, project, headers = await a_facilitator(db_session)

    assert await read_history(client, project.id, headers) == []


# Behaviour 7 — a halt travels beside the state, not inside it (ENG-605).


async def test_a_halted_session_says_it_is_waiting_for_a_person(client, db_session):
    """`needs_person` travels beside `state`, never inside it, and `status` never leaks.

    ENG-605 reverses the decision this test used to record. Before it, a halted room read
    exactly like one running normally — the Desk's only real surface had no way to say a
    conversation was stuck waiting for a person. What still holds: `state` keeps the three
    values RF-06's rule already settled (`session_end.py`), and `status` — the room's own
    machine, `IRSessionStatus` — still never reaches the wire. What no longer holds: the
    halt is not silent any more. It has its own field.
    """
    _user, project, headers = await a_facilitator(db_session)
    session = await a_session(db_session, project_id=project.id)
    await room.mark_needs_person(db_session, session)

    [card] = await read_history(client, project.id, headers)

    assert card["needs_person"] is True
    assert card["state"] == "in_progress"
    assert "status" not in card


async def test_an_ordinary_open_session_says_it_does_not_need_a_person(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    await a_session(db_session, project_id=project.id)

    [card] = await read_history(client, project.id, headers)

    assert card["needs_person"] is False
    assert card["state"] == "in_progress"


async def test_a_turn_that_lands_lifts_the_halt(client, db_session):
    """`needs_person` reads live off the session's status, not a value stamped once.

    `append_exchange` is what actually clears `NEEDS_PERSON` (`sessions.py`); reaching it
    here through the real service is what proves the card is derived, not cached.
    """
    _user, project, headers = await a_facilitator(db_session)
    session = await a_session(db_session, project_id=project.id)
    await room.mark_needs_person(db_session, session)

    await room.append_exchange(db_session, session, team_utterance="oi", guide_response="ok")

    [card] = await read_history(client, project.id, headers)

    assert card["needs_person"] is False


async def test_a_session_that_ended_is_never_reported_as_still_halted(client, db_session):
    """A completed session cannot arrive here carrying `NEEDS_PERSON`: `apply_coverage` only
    closes a session whose status is already `IN_PROGRESS`, so today's state machine has no
    path from a halt straight to `DONE`. The assertion is kept: it is the contract the field
    promises, not an artifact of which paths exist today.
    """
    _user, project, headers = await a_facilitator(db_session)
    completed = await a_session(db_session, project_id=project.id)
    await room.apply_coverage(db_session, completed.id, dict.fromkeys(element_keys(P), ENGAGED))

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "complete"
    assert card["needs_person"] is False


async def test_a_halted_session_idle_for_seven_hours_still_reads_as_needing_a_person(
    client, db_session
):
    _user, project, headers = await a_facilitator(db_session)
    halted = await a_session(db_session, project_id=project.id)
    await room.mark_needs_person(db_session, halted)
    halted.updated_at = datetime.now(UTC) - timedelta(hours=7)
    await db_session.commit()

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "in_progress"
    assert card["needs_person"] is True


async def test_the_cards_shape_names_every_field_the_desk_reads(client, db_session):
    """`needs_person` cannot silently disappear: `TeamSessionResponse` requires it under
    `extra="forbid"`, so a `_card` that forgot to fill it would fail to build rather than
    serve a card silently missing the field.
    """
    _user, project, headers = await a_facilitator(db_session)
    await a_session(db_session, project_id=project.id)

    [card] = await read_history(client, project.id, headers)

    assert set(card) == {
        "session_id",
        "pericope",
        "started_at",
        "ended_at",
        "duration_minutes",
        "state",
        "needs_person",
        "last_halt",
        "halt",
        "warned_at",
        "attended_at",
        "attended_by",
        "person_arrived_at",
        "coverage",
    }
