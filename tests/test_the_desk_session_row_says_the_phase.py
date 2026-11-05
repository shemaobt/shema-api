"""The Desk's session row says how far the session has gone: its **Phase** (ENG-2166)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRRelease, IRSegment, IRSession, IRTake
from app.services.internalization_room import sessions as room
from app.services.internalization_room.back_translation import Finding, FindingKind
from app.services.internalization_room.sessions import back_translation_of, save_back_translation
from tests.baker import (
    grant_facilitator_app_role,
    keep_a_take,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.room_harness import a_scene_rehearsal

URL = "/api/facilitator/sessions"
NOON = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
LOST_CANON = "c" * 40
FAMILIARIZATION = {"at": "familiarization"}
ARTICULATION = {"at": "articulation", "part": 1, "fenced": False}
ENSAIO_FINAL = {"at": "ensaio_final"}


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
    from app.services.auth.issue_tokens import issue_tokens

    language = await make_language(db, name=f"Lang {name}", code=name[:3].lower())
    team = await make_project(db, language.id, name=f"Equipe {name}")
    user = await make_user(db, email=f"{name.lower()}@example.com")
    await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return team, {"Authorization": f"Bearer {access}"}


async def a_session(
    db: AsyncSession, team, *, pericope: str = "P03", last_activity: datetime = NOON
) -> IRSession:
    session = await room.create_session(db, pericope=pericope, project_id=team.id, language="pt")
    session = await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")
    session.updated_at = last_activity
    await db.commit()
    await db.refresh(session)
    return session


async def the_moment_is(db: AsyncSession, session: IRSession, after: dict) -> None:
    guide = {**session.messages[-1], "moment": {"after": after}}
    session.messages = [*session.messages[:-1], guide]
    await db.commit()


async def a_kept_part(db: AsyncSession, session: IRSession, *, pass_number: int = 1) -> IRTake:
    return await keep_a_take(
        db, session, audio=f"parte passe {pass_number}".encode(), ordinal=1, pass_number=pass_number
    )


async def a_stretch(
    db: AsyncSession,
    session: IRSession,
    take: IRTake,
    *,
    transcript: str | None,
    superseded_at: datetime | None = None,
    ordinal: int = 1,
) -> None:
    db.add(
        IRSegment(
            session_id=session.id,
            project_id=session.project_id,
            ordinal=ordinal,
            take_id=take.id,
            starts_ms=0,
            ends_ms=9000,
            transcript=transcript,
            superseded_at=superseded_at,
        )
    )
    await db.commit()


async def a_told_stretch(db: AsyncSession, session: IRSession) -> None:
    await a_stretch(db, session, await a_kept_part(db, session), transcript="Noemi voltou.")


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


async def a_check_round(
    db: AsyncSession, session: IRSession, findings: list[Finding] | None = None
) -> None:
    state = back_translation_of(session)
    state.findings = findings or []
    state.checked = not findings
    state.checked_at = NOON
    await save_back_translation(db, session, state)


async def rows(client, headers, **params) -> list[dict]:
    answer = await client.get(URL, headers=headers, params=params)
    assert answer.status_code == 200, answer.text
    return answer.json()["sessions"]


async def the_phase(client, headers) -> str:
    [row] = await rows(client, headers)
    return row["phase"]


async def test_a_session_with_turns_only_reads_conversation(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    await a_session(db_session, team)

    assert await the_phase(client, headers) == "conversation"


async def test_a_session_with_scene_rehearsals_sent_no_part_of_the_ensaio_final_and_the_moment_at_an_articulacao_reads_conversation(  # noqa: E501
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    rehearsal = await a_scene_rehearsal(db_session, session, 1)
    rehearsal.sent_at = NOON
    await db_session.commit()
    await the_moment_is(db_session, session, ARTICULATION)

    assert await the_phase(client, headers) == "conversation"


async def test_a_session_whose_moment_is_the_ensaio_final_with_no_take_reads_rehearsal(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await the_moment_is(db_session, session, ENSAIO_FINAL)

    assert await the_phase(client, headers) == "rehearsal"


async def test_a_session_with_a_kept_part_of_the_ensaio_final_whose_moment_went_back_to_the_familiarizacao_reads_rehearsal(  # noqa: E501
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_kept_part(db_session, session)
    await the_moment_is(db_session, session, FAMILIARIZATION)

    assert await the_phase(client, headers) == "rehearsal"


async def test_a_session_with_one_told_stretch_reads_telling_back(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_told_stretch(db_session, session)

    assert await the_phase(client, headers) == "telling_back"


@pytest.mark.parametrize(
    "no_words",
    [pytest.param(None, id="no transcript"), pytest.param("", id="an empty transcript")],
)
async def test_a_session_with_a_kept_part_and_only_a_cut_piece_not_yet_told_reads_rehearsal(
    client, db_session, no_words
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    part = await a_kept_part(db_session, session)
    await a_stretch(db_session, session, part, transcript=no_words)

    assert await the_phase(client, headers) == "rehearsal"


async def test_a_session_whose_check_returned_findings_reads_check(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_told_stretch(db_session, session)
    await a_check_round(
        db_session, session, [Finding(kind=FindingKind.MISSING, note="faltou Moabe")]
    )

    assert await the_phase(client, headers) == "check"


async def test_a_session_whose_check_came_back_clean_reads_check(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_told_stretch(db_session, session)
    await a_check_round(db_session, session)

    assert await the_phase(client, headers) == "check"


async def test_a_session_with_a_release_then_one_part_re_recorded_still_reads_check(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_told_stretch(db_session, session)
    await a_release(db_session, session)
    again = await a_kept_part(db_session, session, pass_number=2)
    await room.retire_the_part_recorded_again(db_session, session, again)
    await db_session.commit()

    assert await the_phase(client, headers) == "check"


async def test_a_panorama_session_reads_conversation(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    await a_session(db_session, team, pericope="OV-Ruth")

    assert await the_phase(client, headers) == "conversation"


async def test_a_session_whose_canon_is_not_kept_with_a_told_stretch_reads_telling_back(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_told_stretch(db_session, session)
    session.canon_pin = LOST_CANON
    await db_session.commit()

    assert await the_phase(client, headers) == "telling_back"


async def test_a_session_whose_passage_was_released_by_another_session_reads_its_own_phase(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    own = await a_session(db_session, team)
    releasing = await a_session(db_session, team, last_activity=NOON + timedelta(minutes=1))
    await a_release(db_session, releasing)

    phases = {row["session_id"]: row["phase"] for row in await rows(client, headers)}

    assert phases == {own.id: "conversation", releasing.id: "check"}


async def test_a_complete_session_with_turns_only_reads_conversation(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    session.ended_at = NOON
    await db_session.commit()

    [row] = await rows(client, headers)

    assert (row["state"], row["phase"]) == ("complete", "conversation")


async def test_a_superseded_stretch_with_words_does_not_count_as_told(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_stretch(
        db_session,
        session,
        await a_kept_part(db_session, session),
        transcript="Noemi voltou.",
        superseded_at=NOON,
    )

    assert await the_phase(client, headers) == "rehearsal"


async def test_a_session_whose_check_was_cleared_by_a_restart_with_a_kept_part_reads_rehearsal(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_session(db_session, team)
    await a_told_stretch(db_session, session)
    await a_check_round(db_session, session)
    await room.start_the_translation_over(db_session, session)

    assert await the_phase(client, headers) == "rehearsal"


async def test_the_listing_of_ten_sessions_makes_as_many_statements_as_the_listing_of_one(
    client, db_session, test_engine
):
    team, headers = await a_facilitated_team(db_session)
    first = await a_session(db_session, team)
    await a_told_stretch(db_session, first)
    statements: list[str] = []

    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", count)
    try:
        await rows(client, headers)
        statements.clear()
        await rows(client, headers)
        for_one = len(statements)

        for minute in range(1, 10):
            session = await a_session(
                db_session, team, last_activity=NOON + timedelta(minutes=minute)
            )
            if minute % 2 == 0:
                await a_told_stretch(db_session, session)
        statements.clear()
        listed = await rows(client, headers)
        for_ten = len(statements)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", count)

    phases = [row["phase"] for row in listed]
    assert (phases.count("telling_back"), phases.count("conversation")) == (5, 5)
    assert for_ten == for_one


@pytest.mark.parametrize(
    "narrowed_by",
    [
        pytest.param(("team_id",), id="by team"),
        pytest.param(("pericope",), id="by passage"),
        pytest.param(("team_id", "pericope"), id="by team and passage"),
    ],
)
async def test_a_page_filtered_by_team_and_passage_carries_the_phase_of_each_row(
    client, db_session, narrowed_by
):
    team, headers = await a_facilitated_team(db_session)
    told = await a_session(db_session, team, pericope="P01")
    await a_told_stretch(db_session, told)
    released = await a_session(
        db_session, team, pericope="P01", last_activity=NOON + timedelta(minutes=1)
    )
    await a_release(db_session, released)
    filters = {"team_id": team.id, "pericope": "P01"}
    params = {name: filters[name] for name in narrowed_by}

    first = await client.get(URL, headers=headers, params={**params, "limit": 1})
    second = await client.get(
        URL, headers=headers, params={**params, "limit": 1, "cursor": first.json()["next_cursor"]}
    )

    assert [
        (row["session_id"], row["phase"])
        for page in (first, second)
        for row in page.json()["sessions"]
    ] == [(released.id, "check"), (told.id, "telling_back")]
