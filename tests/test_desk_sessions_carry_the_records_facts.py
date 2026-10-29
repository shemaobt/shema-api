"""The Desk's «Sessões» row carries what the session record opens with (ENG-2003): when the
session started, the scene it is on, and the moment the room left it in."""

from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRSession
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.coverage import CoverageStatus
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

URL = "/api/facilitator/sessions"
ENGAGED = CoverageStatus.ENGAGED.value
ARTICULATION = {"after": {"at": "articulation", "part": 2, "fenced": False}}
STARTED = datetime(2026, 10, 28, 14, 0, tzinfo=UTC)


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


async def a_facilitated_team(db: AsyncSession) -> tuple[object, dict[str, str]]:
    from app.services.auth.issue_tokens import issue_tokens

    language = await make_language(db, name="Lang Rute", code="rut")
    team = await make_project(db, language.id, name="Equipe Rute")
    user = await make_user(db, email="fac@example.com")
    await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return team, {"Authorization": f"Bearer {access}"}


async def a_spoken_session(db: AsyncSession, team, pericope: str) -> IRSession:
    session = await room.create_session(db, pericope=pericope, project_id=team.id, language="pt")
    return await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")


async def the_only_row(client, headers) -> dict:
    answer = await client.get(URL, headers=headers)
    assert answer.status_code == 200, answer.text
    [row] = answer.json()["sessions"]
    return row


async def test_a_session_row_says_when_it_started_with_its_offset(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    session = await a_spoken_session(db_session, team, "P03")
    session.created_at = STARTED
    await db_session.commit()

    row = await the_only_row(client, headers)

    started = datetime.fromisoformat(row["started_at"])
    assert started.utcoffset() is not None
    assert started == STARTED


async def test_a_session_in_articulation_on_scene_2_carries_that_moment_and_that_scene(
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    session = await a_spoken_session(db_session, team, "P03")
    guide = {
        **session.messages[-1],
        "moment": {"after": {"at": "articulation", "part": 2, "fenced": False}},
    }
    session.messages = [*session.messages[:-1], guide]
    await db_session.commit()
    scene_one = [element.key for element in elements_for("P03") if element.scene == 1]
    await room.apply_coverage(db_session, session.id, dict.fromkeys(scene_one, ENGAGED))

    row = await the_only_row(client, headers)

    assert (row["moment"], row["scene"]) == (
        {"at": "articulation", "part": 2, "parts": 3},
        "S2",
    )


@pytest.mark.parametrize(
    "pericope",
    [
        pytest.param("P03", id="a session before its first guide line"),
        pytest.param("OV-Ruth", id="a panorama"),
    ],
)
async def test_a_session_before_its_first_guide_line_and_a_panorama_carry_no_moment_and_no_scene(
    client, db_session, pericope
):
    team, headers = await a_facilitated_team(db_session)
    session = await room.create_session(
        db_session, pericope=pericope, project_id=team.id, language="pt"
    )
    session.messages = [{"role": "team", "text": "oi", "opening_note": True}]
    await db_session.commit()

    row = await the_only_row(client, headers)

    assert (row["moment"], row["scene"]) == (None, None)


async def test_a_session_whose_canon_is_gone_is_listed_with_no_scene_and_no_moment_and_the_list_still_answers(  # noqa: E501
    client, db_session
):
    team, headers = await a_facilitated_team(db_session)
    lost = await a_spoken_session(db_session, team, "P03")
    lost.messages = [*lost.messages[:-1], {**lost.messages[-1], "moment": ARTICULATION}]
    lost.canon_pin = "c" * 40
    unmoved = await a_spoken_session(db_session, team, "P03")
    unmoved.canon_pin = "d" * 40
    unmoved.messages = [
        {**unmoved.messages[0]},
        {k: v for k, v in unmoved.messages[-1].items() if k != "moment"},
    ]
    kept = await a_spoken_session(db_session, team, "P14")
    await db_session.commit()

    answer = await client.get(URL, headers=headers)

    assert answer.status_code == 200, answer.text
    rows = {row["session_id"]: row for row in answer.json()["sessions"]}
    assert (rows[lost.id]["moment"], rows[lost.id]["scene"]) == (None, None)
    assert (rows[unmoved.id]["moment"], rows[unmoved.id]["scene"]) == (None, None)
    assert rows[kept.id]["scene"] == "S1"


async def test_a_spoken_panorama_carries_no_moment_and_no_scene(client, db_session):
    team, headers = await a_facilitated_team(db_session)
    panorama = await a_spoken_session(db_session, team, "OV-Ruth")
    panorama.messages = [
        *panorama.messages[:-1],
        {**panorama.messages[-1], "moment": ARTICULATION},
    ]
    await db_session.commit()

    row = await the_only_row(client, headers)

    assert (row["moment"], row["scene"]) == (None, None)
