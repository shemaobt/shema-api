from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRRelease, IRSession
from app.services.internalization_room import sessions as room
from app.services.internalization_room.archives import archive_pericope
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.coverage import CoverageStatus
from tests.baker import (
    grant_facilitator_app_role,
    keep_a_take,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.release_harness import a_claimed_device, team_headers

URL = "/api/facilitator/sessions"
SMALL_PASSAGE = "P14"
ENGAGED = CoverageStatus.ENGAGED.value
NOON = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


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


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def a_team(db: AsyncSession, name: str):
    language = await make_language(db, name=f"Lang {name}", code=name.split()[-1][:3].lower())
    return await make_project(db, language.id, name=name)


async def a_facilitator_of(db: AsyncSession, *teams, email: str) -> dict[str, str]:
    user = await make_user(db, email=email)
    for team in teams:
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    return await auth_header(db, user)


async def an_admin(db: AsyncSession) -> dict[str, str]:
    user = await make_user(db, email="admin@example.com", is_platform_admin=True)
    await grant_facilitator_app_role(db, user.id)
    return await auth_header(db, user)


async def a_session(
    db: AsyncSession,
    team,
    *,
    pericope: str = "P03",
    language: str = "pt",
    last_activity: datetime = NOON,
    guide_lines: int = 1,
) -> IRSession:
    session = await room.create_session(
        db, pericope=pericope, project_id=team.id, language=language
    )
    for _ in range(guide_lines):
        session = await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")
    session.updated_at = last_activity
    await db.commit()
    await db.refresh(session)
    return session


async def a_rehearsal_part(db: AsyncSession, session: IRSession, number: int, *, pass_number=1):
    await keep_a_take(
        db,
        session,
        audio=f"parte {number} passe {pass_number}".encode(),
        ordinal=number,
        pass_number=pass_number,
    )


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


async def engage(db: AsyncSession, session: IRSession, count: int) -> None:
    keys = [element.key for element in labelled_elements(session.pericope)[:count]]
    await room.apply_coverage(db, session.id, dict.fromkeys(keys, ENGAGED))


async def read(client, headers, **params) -> dict:
    answer = await client.get(URL, headers=headers, params=params)
    assert answer.status_code == 200, answer.text
    return answer.json()


async def test_two_teams_with_sessions_on_different_passages_one_in_english_read_as_one_list_newest_activity_first_each_with_its_teams_name_and_language(  # noqa: E501
    client, db_session
):
    ruth = await a_team(db_session, "Equipe Rute")
    naomi = await a_team(db_session, "Equipe Noemi")
    headers = await a_facilitator_of(db_session, ruth, naomi, email="fac@example.com")
    older = await a_session(db_session, ruth, pericope="P03", last_activity=NOON)
    newer = await a_session(
        db_session,
        naomi,
        pericope="P05",
        language="en",
        last_activity=NOON + timedelta(minutes=5),
    )

    listed = (await read(client, headers))["sessions"]

    assert [
        (item["session_id"], item["team_id"], item["team_name"], item["pericope"], item["language"])
        for item in listed
    ] == [
        (newer.id, naomi.id, "Equipe Noemi", "P05", "en"),
        (older.id, ruth.id, "Equipe Rute", "P03", "pt"),
    ]
    for item in listed:
        book = await client.get(
            f"/api/facilitator/teams/{item['team_id']}/pericopes", headers=headers
        )
        served = {row["pericope"]: row["reference"] for row in book.json()}
        assert item["reference"] == served[item["pericope"]]


async def test_a_session_with_7_guide_lines_5_of_19_elements_engaged_2_kept_rehearsals_and_a_release_reads_7_turns_5_of_19_2_rehearsals_and_has_a_release(  # noqa: E501
    client, db_session
):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    session = await a_session(db_session, team, pericope=SMALL_PASSAGE, guide_lines=7)
    await engage(db_session, session, 5)
    await a_rehearsal_part(db_session, session, 1)
    await a_rehearsal_part(db_session, session, 2)
    await a_rehearsal_part(db_session, session, 2, pass_number=2)
    await a_release(db_session, session)

    [item] = (await read(client, headers))["sessions"]

    assert (
        item["turns"],
        item["engaged_elements"],
        item["total_elements"],
        item["kept_rehearsals"],
        item["has_release"],
    ) == (7, 5, 19, 2, True)


async def test_a_panorama_session_is_listed_0_of_0(client, db_session):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    panorama = await a_session(db_session, team, pericope="OV-Ruth")

    [item] = (await read(client, headers))["sessions"]

    assert (
        item["session_id"],
        item["reference"],
        item["engaged_elements"],
        item["total_elements"],
    ) == (panorama.id, None, 0, 0)


async def test_a_facilitator_of_team_a_does_not_see_team_bs_sessions_an_admin_sees_both(
    client, db_session
):
    team_a = await a_team(db_session, "Equipe A")
    team_b = await a_team(db_session, "Equipe B")
    facilitator_of_a = await a_facilitator_of(db_session, team_a, email="a@example.com")
    admin = await an_admin(db_session)
    of_a = await a_session(db_session, team_a)
    of_b = await a_session(db_session, team_b, last_activity=NOON + timedelta(minutes=1))

    seen_by_a = [item["session_id"] for item in (await read(client, facilitator_of_a))["sessions"]]
    seen_by_admin = [item["session_id"] for item in (await read(client, admin))["sessions"]]

    assert seen_by_a == [of_a.id]
    assert seen_by_admin == [of_b.id, of_a.id]


async def test_a_zeroed_pericopes_sessions_are_absent(client, db_session):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    zeroed = await a_session(db_session, team, pericope="P03")
    kept = await a_session(db_session, team, pericope="P05")
    admin = await make_user(db_session, email="zerar@example.com", is_platform_admin=True)
    await archive_pericope(db_session, admin, project_id=team.id, pericope=zeroed.pericope)

    listed = [item["session_id"] for item in (await read(client, headers))["sessions"]]

    assert listed == [kept.id]


async def test_a_session_nobody_entered_is_absent(client, db_session):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    entered = await a_session(db_session, team)
    await room.create_session(db_session, pericope="P05", project_id=team.id)

    listed = [item["session_id"] for item in (await read(client, headers))["sessions"]]

    assert listed == [entered.id]


async def test_60_sessions_read_as_50_and_the_cursor_reads_the_other_10_in_the_same_order(
    client, db_session
):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    sessions = [
        await a_session(db_session, team, last_activity=NOON + timedelta(minutes=minute))
        for minute in range(60)
    ]
    newest_first = [session.id for session in reversed(sessions)]

    first = await read(client, headers)
    second = await read(client, headers, cursor=first["next_cursor"])

    assert [item["session_id"] for item in first["sessions"]] == newest_first[:50]
    assert [item["session_id"] for item in second["sessions"]] == newest_first[50:]
    assert second["next_cursor"] is None


async def test_the_listener_count_is_null(client, db_session):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    await a_session(db_session, team)

    [item] = (await read(client, headers))["sessions"]

    assert item["listener_count"] is None


async def test_reading_the_list_leaves_every_session_unchanged(client, db_session):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    await a_session(db_session, team, pericope="P03")
    await a_session(db_session, team, pericope="OV-Ruth", last_activity=NOON + timedelta(hours=1))

    def snapshot(rows):
        return sorted(
            (row.id, row.updated_at, row.version, row.status, row.attended_at) for row in rows
        )

    before = snapshot((await db_session.execute(select(IRSession))).scalars().all())
    await read(client, headers)
    after = snapshot((await db_session.execute(select(IRSession))).scalars().all())

    assert after == before
    assert not db_session.dirty
    assert not db_session.new


async def test_the_list_is_refused_without_the_facilitator_role_and_to_a_team_tablets_credential(
    client, db_session
):
    team, tablet = await a_claimed_device(db_session)
    member = await make_user(db_session, email="member@example.com")
    await make_project_user_access(db_session, team.id, member.id, role=ProjectRole.MEMBER)

    without_the_role = await client.get(URL, headers=await auth_header(db_session, member))
    from_a_tablet = await client.get(URL, headers=team_headers(tablet))

    assert without_the_role.status_code == 403
    assert from_a_tablet.status_code == 401


async def test_a_session_reads_the_same_engaged_total_and_state_in_the_teams_list_and_in_this_list(
    client, db_session
):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    earlier = await a_session(db_session, team, pericope=SMALL_PASSAGE)
    await engage(db_session, earlier, 6)
    later = await a_session(db_session, team, pericope=SMALL_PASSAGE)
    await engage(db_session, later, 2)
    later = await room.mark_needs_person(db_session, later)
    earlier.updated_at = NOON
    later.updated_at = NOON + timedelta(hours=1)
    await db_session.commit()

    [item] = (await read(client, headers, limit=1))["sessions"]
    cards = (await client.get(f"/api/facilitator/teams/{team.id}/sessions", headers=headers)).json()
    card = next(card for card in cards if card["session_id"] == later.id)

    assert item["session_id"] == later.id
    assert (item["engaged_elements"], item["total_elements"]) == (
        sum(1 for bead in card["coverage"] if bead["status"] == ENGAGED),
        len(card["coverage"]),
    )
    assert item["state"] == ("needs_person" if card["needs_person"] else card["state"])
    assert item["state"] == "needs_person"


async def test_a_session_whose_team_no_longer_exists_leaves_the_rest_of_the_list_readable(
    client, db_session
):
    team = await a_team(db_session, "Equipe Rute")
    admin = await an_admin(db_session)
    listed = await a_session(db_session, team)
    orphan = await a_session(db_session, team, last_activity=NOON + timedelta(minutes=1))
    orphan.project_id = "uma-equipe-que-nao-existe"
    await db_session.commit()

    sessions = (await read(client, admin))["sessions"]

    assert [item["session_id"] for item in sessions] == [listed.id]


async def test_a_session_zeroed_while_the_page_is_read_is_left_out_and_the_page_still_reads(
    client, db_session, test_engine
):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    kept = await a_session(db_session, team, pericope="P03")
    zeroed = await a_session(db_session, team, pericope="P05", last_activity=NOON + timedelta(1))
    zeroed_mid_read = {"done": False}

    def zero_after_the_page_query(conn, cursor, statement, parameters, context, executemany):
        if zeroed_mid_read["done"] or "JOIN projects" not in statement:
            return
        zeroed_mid_read["done"] = True
        other = conn.connection.cursor()
        other.execute("UPDATE ir_sessions SET archive_id = 'arquivo' WHERE id = ?", (zeroed.id,))
        other.close()

    event.listen(test_engine.sync_engine, "after_cursor_execute", zero_after_the_page_query)
    try:
        answer = await client.get(URL, headers=headers)
    finally:
        event.remove(test_engine.sync_engine, "after_cursor_execute", zero_after_the_page_query)

    assert zeroed_mid_read["done"]
    assert answer.status_code == 200, answer.text
    assert [item["session_id"] for item in answer.json()["sessions"]] == [kept.id]


async def test_the_turns_are_the_guide_lines_of_the_conversation_and_not_of_the_telling_back_verdict(  # noqa: E501
    client, db_session
):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    session = await a_session(db_session, team, guide_lines=3)
    for _ in range(2):
        session = await room.append_exchange(
            db_session, session, team_utterance="", guide_response="veredito", told_back="contou"
        )

    [item] = (await read(client, headers))["sessions"]

    assert item["turns"] == 3


async def test_a_rehearsal_take_stamped_by_an_archive_is_not_a_kept_rehearsal(client, db_session):
    team = await a_team(db_session, "Equipe Rute")
    headers = await a_facilitator_of(db_session, team, email="fac@example.com")
    session = await a_session(db_session, team)
    await a_rehearsal_part(db_session, session, 1)
    stamped = await keep_a_take(db_session, session, audio=b"parte 2", ordinal=2, pass_number=1)
    stamped.archive_id = "arquivo"
    await db_session.commit()

    [item] = (await read(client, headers))["sessions"]

    assert item["kept_rehearsals"] == 1


async def test_a_page_spanning_six_teams_is_read_in_as_many_statements_as_one_spanning_two(
    client, db_session, test_engine
):
    admin = await an_admin(db_session)
    teams = [await a_team(db_session, f"Equipe {name}") for name in ("Rute", "Noemi")]
    for minute, team in enumerate(teams):
        await a_session(db_session, team, last_activity=NOON + timedelta(minutes=minute))
    statements: list[str] = []

    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", count)
    try:
        await read(client, admin)
        statements.clear()
        await read(client, admin)
        for_two = len(statements)

        more = [
            await a_team(db_session, f"Equipe {name}")
            for name in ("Boaz", "Orfa", "Elimeleque", "Quiliom")
        ]
        for minute, team in enumerate(more, start=2):
            await a_session(db_session, team, last_activity=NOON + timedelta(minutes=minute))
        statements.clear()
        listed = await read(client, admin)
        for_six = len(statements)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", count)

    assert len({item["team_id"] for item in listed["sessions"]}) == 6
    assert for_six == for_two


async def test_two_teams_on_one_passage_each_read_their_own_engaged_elements(client, db_session):
    admin = await an_admin(db_session)
    ruth = await a_team(db_session, "Equipe Rute")
    naomi = await a_team(db_session, "Equipe Noemi")
    of_ruth = await a_session(db_session, ruth, pericope=SMALL_PASSAGE)
    await engage(db_session, of_ruth, 6)
    of_naomi = await a_session(db_session, naomi, pericope=SMALL_PASSAGE)
    await engage(db_session, of_naomi, 2)

    listed = (await read(client, admin))["sessions"]

    assert {item["team_id"]: item["engaged_elements"] for item in listed} == {
        ruth.id: 6,
        naomi.id: 2,
    }
