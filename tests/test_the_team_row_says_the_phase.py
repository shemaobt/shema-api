"""The team listing's row and the team detail say the **Phase** of the session on the team's
active passage: the session the pericope listing names there, or nothing (ENG-2189)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRRelease, IRSegment, IRSession
from app.db.models.project import ProjectUserAccess
from app.services.auth.issue_tokens import issue_tokens
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.sessions import back_translation_of, save_back_translation
from tests.baker import (
    grant_facilitator_app_role,
    grant_room_app_role,
    having_finished_the_passage,
    keep_a_take,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    open_ir_session,
)

TEAMS = "/api/facilitator/teams"
RUTH = [meaning_map.pericope_num for meaning_map in load_book("Ruth")]
ESTHER = [meaning_map.pericope_num for meaning_map in load_book("Esther")]
JONAH = [meaning_map.pericope_num for meaning_map in load_book("Jonah")]
FIRST, SECOND = RUTH[0], RUTH[1]
NOON = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
LOST_CANON = "c" * 40


@pytest.fixture()
async def client(db_session: AsyncSession):
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


async def a_facilitated_team(db: AsyncSession, name: str = "Rute") -> tuple[object, dict[str, str]]:
    language = await make_language(db, name=f"Lang {name}", code=name[:3].lower())
    team = await make_project(db, language.id, name=f"Equipe {name}")
    user = await make_user(db, email=f"{name.lower()}@example.com")
    await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return team, {"Authorization": f"Bearer {access}"}


async def another_team_of_the_facilitator(db: AsyncSession, team, name: str):
    other = await make_project(db, team.language_id, name=f"Equipe {name}")
    facilitator = (
        await db.execute(
            select(ProjectUserAccess.user_id).where(ProjectUserAccess.project_id == team.id)
        )
    ).scalar_one()
    await make_project_user_access(db, other.id, facilitator, role=ProjectRole.FACILITATOR)
    return other


async def a_consultant(db: AsyncSession) -> dict[str, str]:
    user = await make_user(db, email="consultora@example.com")
    await grant_room_app_role(db, user.id, "consultant")
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def a_session(db: AsyncSession, team, *, pericope: str = FIRST) -> IRSession:
    session = await room.create_session(db, pericope=pericope, project_id=team.id, language="pt")
    return await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")


async def last_active_at(db: AsyncSession, session: IRSession, moment: datetime) -> None:
    session.updated_at = moment
    await db.commit()


async def a_told_stretch(db: AsyncSession, session: IRSession) -> None:
    take = await keep_a_take(db, session, audio=f"parte de {session.id}".encode(), ordinal=1)
    db.add(
        IRSegment(
            session_id=session.id,
            project_id=session.project_id,
            ordinal=1,
            take_id=take.id,
            starts_ms=0,
            ends_ms=9000,
            transcript="Noemi voltou.",
        )
    )
    await db.commit()


async def a_release(db: AsyncSession, session: IRSession) -> None:
    db.add(
        IRRelease(
            session_id=session.id,
            project_id=session.project_id,
            pericope=session.pericope,
            version=1,
            package_sha256="a" * 64,
            packet={},
        )
    )
    await db.commit()


async def a_clean_check_round(db: AsyncSession, session: IRSession) -> None:
    state = back_translation_of(session)
    state.findings = []
    state.checked = True
    state.checked_at = NOON
    await save_back_translation(db, session, state)


async def zerar(client, headers, team, pericope: str = FIRST) -> None:
    answer = await client.post(
        f"/api/internalization-room/facilitator/projects/{team.id}/passages/{pericope}/archive",
        headers=headers,
    )
    assert answer.status_code == 200, answer.text


async def the_row(client, headers, team, **params) -> dict:
    answer = await client.get(TEAMS, headers=headers, params=params)
    assert answer.status_code == 200, answer.text
    return next(row for row in answer.json()["teams"] if row["team_id"] == team.id)


async def the_detail(client, headers, team) -> dict:
    answer = await client.get(f"{TEAMS}/{team.id}", headers=headers)
    assert answer.status_code == 200, answer.text
    return answer.json()


async def the_session_the_pericope_listing_names(client, headers, team, pericope: str) -> str:
    answer = await client.get(f"{TEAMS}/{team.id}/pericopes", headers=headers)
    assert answer.status_code == 200, answer.text
    return next(entry for entry in answer.json() if entry["pericope"] == pericope)["session_id"]


async def test_a_team_whose_session_on_its_active_passage_has_a_told_stretch_reads_telling_back(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    await a_told_stretch(db_session, await a_session(db_session, team))

    assert (await the_row(client, headers, team))["phase"] == "telling_back"


async def test_a_team_that_just_closed_a_passage_with_no_session_on_the_next_reads_no_phase_though_the_closed_passages_session_reached_check(  # noqa: E501
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    closed = await having_finished_the_passage(db_session, await a_session(db_session, team))
    await a_clean_check_round(db_session, closed)

    row = await the_row(client, headers, team)
    detail = await the_detail(client, headers, team)

    assert row["active_passage"]["pericope"] == SECOND
    assert (row["phase"], detail["phase"]) == (None, None)


async def test_a_team_that_closed_every_passage_of_every_served_book_reads_no_phase(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    for passage in [*RUTH, *ESTHER, *JONAH]:
        session = await open_ir_session(db_session, pericope=passage, project_id=team.id)
        await having_finished_the_passage(db_session, session)

    row = await the_row(client, headers, team)
    detail = await the_detail(client, headers, team)

    assert row["active_passage"] is None
    assert (row["phase"], detail["phase"]) == (None, None)


async def test_a_team_whose_active_passage_was_zeroed_with_no_new_session_reads_no_phase(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    await a_told_stretch(db_session, await a_session(db_session, team))
    await zerar(client, headers, team)

    row = await the_row(client, headers, team)
    detail = await the_detail(client, headers, team)

    assert row["active_passage"]["pericope"] == FIRST
    assert (row["phase"], detail["phase"]) == (None, None)


async def _the_older_holds_the_take(db: AsyncSession, older: IRSession, latest: IRSession):
    await a_told_stretch(db, older)
    return older, "telling_back"


async def _the_latest_holds_the_take(db: AsyncSession, older: IRSession, latest: IRSession):
    await a_told_stretch(db, latest)
    return latest, "telling_back"


async def _both_hold_a_take(db: AsyncSession, older: IRSession, latest: IRSession):
    await a_told_stretch(db, older)
    await keep_a_take(db, latest, audio=b"parte da mais recente", ordinal=1)
    return latest, "rehearsal"


@pytest.mark.parametrize(
    "seeding",
    [
        pytest.param(_the_older_holds_the_take, id="the older holds the take"),
        pytest.param(_the_latest_holds_the_take, id="the latest holds the take"),
        pytest.param(_both_hold_a_take, id="both hold a take"),
    ],
)
async def test_with_two_live_sessions_on_the_active_passage_the_row_reads_the_phase_of_the_session_the_pericope_listing_names(  # noqa: E501
    client, db_session, seeding
):
    team, headers = await a_facilitated_team(db_session)
    older = await a_session(db_session, team)
    latest = await a_session(db_session, team)
    named, phase = await seeding(db_session, older, latest)
    await last_active_at(db_session, older, NOON)
    await last_active_at(db_session, latest, NOON + timedelta(minutes=1))

    row = await the_row(client, headers, team)
    detail = await the_detail(client, headers, team)

    assert await the_session_the_pericope_listing_names(client, headers, team, FIRST) == named.id
    assert (row["phase"], detail["phase"]) == (phase, phase)


async def _told(db: AsyncSession, session: IRSession) -> None:
    await a_told_stretch(db, session)


async def _checked(db: AsyncSession, session: IRSession) -> None:
    await a_told_stretch(db, session)
    await a_clean_check_round(db, session)


@pytest.mark.parametrize(
    ("reaching", "phase"),
    [
        pytest.param(_told, "telling_back", id="telling back"),
        pytest.param(_checked, "check", id="check"),
    ],
)
async def test_the_row_and_the_team_detail_give_the_same_phase_for_the_same_team(
    client, db_session, reaching, phase
):
    team, headers = await a_facilitated_team(db_session)
    await reaching(db_session, await a_session(db_session, team))

    row = await the_row(client, headers, team)
    detail = await the_detail(client, headers, team)

    assert (row["phase"], detail["phase"]) == (phase, phase)


async def test_the_listing_of_ten_teams_makes_as_many_statements_as_the_listing_of_one(
    client, db_session, test_engine
):
    async def every_fact_on(team) -> None:
        session = await a_session(db_session, team)
        await a_told_stretch(db_session, session)
        await a_release(db_session, session)

    team, headers = await a_facilitated_team(db_session)
    await every_fact_on(team)
    statements: list[str] = []

    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", count)
    try:
        await client.get(TEAMS, headers=headers)
        statements.clear()
        await client.get(TEAMS, headers=headers)
        for_one = len(statements)

        for number in range(9):
            await every_fact_on(
                await another_team_of_the_facilitator(db_session, team, f"Outra {number}")
            )
        statements.clear()
        listed = (await client.get(TEAMS, headers=headers)).json()["teams"]
        for_ten = len(statements)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", count)

    assert [row["phase"] for row in listed] == ["check"] * 10
    assert for_ten == for_one


async def test_a_team_that_has_never_met_reads_no_phase(client, db_session):
    team, headers = await a_facilitated_team(db_session)

    assert (await the_row(client, headers, team))["phase"] is None


async def test_an_archived_session_never_counts_a_zeroed_session_with_a_told_stretch_and_a_new_session_with_turns_only_reads_conversation(  # noqa: E501
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    zeroed = await a_session(db_session, team)
    await a_told_stretch(db_session, zeroed)
    await a_clean_check_round(db_session, zeroed)
    await zerar(client, headers, team)
    await a_session(db_session, team)

    assert (await the_row(client, headers, team))["phase"] == "conversation"


async def test_a_session_opened_with_no_turn_yet_reads_conversation_on_the_teams_row(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    await open_ir_session(db_session, pericope=FIRST, project_id=team.id)

    assert (await the_row(client, headers, team))["phase"] == "conversation"


@pytest.mark.parametrize(
    ("told", "phase"),
    [
        pytest.param(True, "telling_back", id="a told stretch"),
        pytest.param(False, "conversation", id="no told stretch"),
    ],
)
async def test_a_team_whose_sessions_canon_is_not_kept_reads_the_phase_of_its_facts_and_the_listing_still_answers(  # noqa: E501
    client, db_session, told, phase
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    if told:
        await a_told_stretch(db_session, session)
    session.canon_pin = LOST_CANON
    await db_session.commit()

    assert (await the_row(client, headers, team))["phase"] == phase


async def test_a_consultant_reads_the_phase_on_a_team_they_have_no_link_to(client, db_session):
    team, _facilitator = await a_facilitated_team(db_session)
    await a_told_stretch(db_session, await a_session(db_session, team))
    consultant = await a_consultant(db_session)

    row = await the_row(client, consultant, team)
    detail = await the_detail(client, consultant, team)

    assert (row["phase"], detail["phase"]) == ("telling_back", "telling_back")


async def test_two_teams_on_the_same_passage_each_read_the_phase_of_their_own_session(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    other = await another_team_of_the_facilitator(db_session, team, "Ester")
    await a_told_stretch(db_session, await a_session(db_session, team))
    await a_session(db_session, other)

    assert (await the_row(client, headers, team))["phase"] == "telling_back"
    assert (await the_row(client, headers, other))["phase"] == "conversation"


@pytest.mark.parametrize(
    "restriction",
    [
        pytest.param({"search": "Rute"}, id="a search"),
        pytest.param({"filter": "in_progress"}, id="a filter"),
    ],
)
async def test_a_row_found_through_a_search_or_a_filter_still_reads_its_phase(
    client, db_session, restriction
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_told_stretch(db_session, session)
    await last_active_at(db_session, session, datetime.now(UTC))

    assert (await the_row(client, headers, team, **restriction))["phase"] == "telling_back"
