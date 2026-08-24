"""ENG-451 — the passage's history: the live conversation first, then newest to oldest.

Four of these carry the slice.

**The order was measured wrong and is fixed here.** Start time alone put a conversation still
going on the 12th under a finished one from the 19th — the one session a facilitator can act
on, buried under one they cannot. Two of the three ordering tests were red before the fix.

**The third was green on arrival and is a guard rather than a discovery.** An abandoned
session leading is what a fix that reached for "not complete" would do, and that is the shape
the obvious fix takes. Proved by mutation rather than left to look thorough: keying the sort
on `COMPLETE` turns exactly that test red and nothing else.

**The project scoping is measured, not inherited.** Every session in the field today has a
null project — the room app does not send its device credential until ENG-454 — so a route
that returned them would look perfectly right on a working installation and would hand every
facilitator every other team's history. A number that is right by accident reads exactly
like a number that is right by construction, so the null case is asserted rather than
assumed.

**The end is the team's last activity, never the moment somebody looked.** The abandoned
session here was left at 15:00 and is asked about the next morning; the card has to say 47
minutes, and has to go on saying 47 minutes however long nobody asks.

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
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.session_end import SESSION_IDLE_LIMIT
from tests.baker import (
    grant_facilitator_app_role,
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


def _ready_comprehension(pericope: str):
    """Calibration, evidence, practice and consent — everything the floor no longer implies.

    ``session_is_done`` stopped being the coverage floor alone: it folds in semantic
    readiness and the team's recording consent, so that a bridge-limited team is not judged
    on Portuguese output. A scenario about *closing* has to carry all of it now.
    """
    from app.services.internalization_room.comprehension.checkpoints import (
        checkpoints_for,
        scene_ids_for,
    )
    from app.services.internalization_room.comprehension.evidence import (
        EvidenceMethod,
        EvidenceObservation,
        EvidenceResult,
    )
    from app.services.internalization_room.comprehension.state import ComprehensionState

    return ComprehensionState(
        ledger=[
            EvidenceObservation(
                id=f"ev-{index}",
                unit_id=checkpoint.id,
                probe_id=f"probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=EvidenceResult.DEMONSTRATED,
            )
            for index, checkpoint in enumerate(checkpoints_for(pericope))
        ],
        practiced_scene_ids=scene_ids_for(pericope),
        recording_consent_given=True,
    )


async def a_session(
    db: AsyncSession,
    *,
    project_id: str | None,
    pericope: str = P,
    opened_at: datetime | None = None,
    last_activity: datetime | None = None,
    ready_to_close: bool = False,
):
    """A conversation, optionally moved back in time so it can be an old one."""
    session = await room.create_session(
        db,
        pericope=pericope,
        project_id=project_id,
        bridge_mode="guided_microchecks" if ready_to_close else None,
    )
    if ready_to_close:
        session = await room.save_comprehension(db, session, _ready_comprehension(pericope))
    if opened_at is not None:
        session.created_at = opened_at
    if last_activity is not None:
        session.updated_at = last_activity
    if opened_at is not None or last_activity is not None:
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
        last_activity=datetime.now(UTC),
    )
    await db_session.commit()

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [still_going.id, finished.id]
    assert history[0]["state"] == "in_progress"


async def test_a_conversation_nobody_closed_does_not_lead_the_history(client, db_session):
    """`in_progress` and nothing else leads, which is a decision this route has to take.

    RF-06's sentence was written when a session was either open or finished. There are three
    states now, and an abandoned conversation carries no end anybody stamped — but it is over,
    and the facilitator can do nothing with it. Leading with it would put the one thing they
    cannot act on where the one thing they can is supposed to be.
    """
    _user, project, headers = await a_facilitator(db_session)
    finished = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 19, 9, 0, tzinfo=UTC),
    )
    finished.ended_at = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    abandoned = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
        last_activity=datetime(2026, 8, 12, 9, 47, tzinfo=UTC),
    )
    await db_session.commit()

    history = await read_history(client, project.id, headers)

    assert [card["session_id"] for card in history] == [finished.id, abandoned.id]
    assert history[1]["state"] == "abandoned"


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
        last_activity=datetime.now(UTC),
    )
    newer = await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
        last_activity=datetime.now(UTC),
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
    session = await a_session(db_session, project_id=project.id, ready_to_close=True)
    session.created_at = datetime.now(UTC) - timedelta(minutes=34)
    await db_session.commit()

    await room.apply_coverage(db_session, session.id, dict.fromkeys(element_keys(P), ENGAGED))

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "complete"
    assert card["ended_at"] is not None
    assert card["duration_minutes"] == 34


async def test_a_conversation_nobody_closed_ends_where_the_team_stopped(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    started = datetime(2026, 8, 20, 14, 13, tzinfo=UTC)
    stopped = datetime(2026, 8, 20, 15, 0, tzinfo=UTC)
    await a_session(db_session, project_id=project.id, opened_at=started, last_activity=stopped)

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "abandoned"
    assert card["duration_minutes"] == 47, (
        "the length ran to the moment somebody asked instead of to the team's last word"
    )
    assert card["ended_at"].startswith("2026-08-20T15:00:00")


async def test_a_quiet_conversation_is_still_going_until_the_limit_is_past(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    await a_session(
        db_session,
        project_id=project.id,
        last_activity=datetime.now(UTC) - SESSION_IDLE_LIMIT + timedelta(minutes=5),
    )

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "in_progress"


# Behaviour 4 — every timestamp says which clock it is on.


async def test_every_moment_on_the_wire_carries_its_offset(client, db_session):
    """A bare `2026-08-20T15:00:00` is read as local by whoever receives it."""
    _user, project, headers = await a_facilitator(db_session)
    await a_session(
        db_session,
        project_id=project.id,
        opened_at=datetime(2026, 8, 20, 14, 13, tzinfo=UTC),
        last_activity=datetime(2026, 8, 20, 15, 0, tzinfo=UTC),
    )

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

    assert set(bead) == {"key", "kind", "label_pt", "label_en", "label_es", "status"}
    assert bead["label_en"]
    assert bead["kind"] == "scene"


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


async def test_the_history_says_nothing_about_the_rooms_own_session_status(client, db_session):
    """`needs_person` is the room's business and is not a state a facilitator reads here.

    Serving it would put a fourth value into a field RF-06 gives three, and a halted
    conversation is still one in progress from the Desk's side.
    """
    _user, project, headers = await a_facilitator(db_session)
    session = await a_session(db_session, project_id=project.id)
    await room.mark_needs_person(db_session, session)

    [card] = await read_history(client, project.id, headers)

    assert card["state"] == "in_progress"
    assert "status" not in card
    assert IRSessionStatus.NEEDS_PERSON.value not in str(card)
