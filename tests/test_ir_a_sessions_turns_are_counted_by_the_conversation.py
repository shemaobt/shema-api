"""ENG-1590 — one reader, the conversation, counts a session's turns wherever it is served.

The Desk sessions list, the turns route and the archive Zerar writes answer the same count for
the same session; the Guide's telling-back verdict is not a turn on any of them.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRSession
from app.services.internalization_room import sessions as room
from app.services.internalization_room.archives import archive_pericope
from tests.baker import (
    grant_facilitator_app_role,
    keep_a_take,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)


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


URL = "/api/facilitator/sessions"
NOON = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


async def a_team(db: AsyncSession):
    language = await make_language(db, name="Lang Rute", code="rut")
    return await make_project(db, language.id, name="Equipe Rute")


async def a_facilitator_of(db: AsyncSession, team) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email="fac@example.com")
    await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def a_session(db: AsyncSession, team, *, guide_lines: int) -> IRSession:
    session = await room.create_session(db, pericope="P03", project_id=team.id, language="pt")
    for _ in range(guide_lines):
        session = await room.append_exchange(db, session, team_utterance="oi", guide_response="ok")
    session.updated_at = NOON
    await db.commit()
    await db.refresh(session)
    return session


async def the_three_counts(client, db_session, team, headers, session: IRSession) -> list[int]:
    on_the_desk = [
        item["turns"]
        for item in (await client.get(URL, headers=headers)).json()["sessions"]
        if item["session_id"] == session.id
    ]
    route = await client.get(
        f"/api/internalization-room/facilitator/sessions/{session.id}/turns", headers=headers
    )
    assert route.status_code == 200, route.text
    admin = await make_user(db_session, email="zerar@example.com", is_platform_admin=True)
    archive = await archive_pericope(
        db_session, admin, project_id=team.id, pericope=session.pericope
    )
    assert archive is not None
    archived = [entry["turns"] for entry in archive.snapshot if entry["session_id"] == session.id]
    return [*on_the_desk, len(route.json()["turns"]), *archived]


async def test_three_guide_replies_and_a_telling_back_verdict_count_three_turns_on_the_desk_the_turns_route_and_the_archive(  # noqa: E501
    client,
    db_session,
):
    team = await a_team(db_session)
    headers = await a_facilitator_of(db_session, team)
    session = await a_session(db_session, team, guide_lines=3)
    await room.append_exchange(
        db_session, session, team_utterance="", guide_response="veredito", told_back="a história"
    )

    assert await the_three_counts(client, db_session, team, headers, session) == [3, 3, 3]


async def test_a_session_without_telling_back_lines_counts_the_same_on_all_three_readers(
    client,
    db_session,
):
    team = await a_team(db_session)
    headers = await a_facilitator_of(db_session, team)
    session = await a_session(db_session, team, guide_lines=2)

    assert await the_three_counts(client, db_session, team, headers, session) == [2, 2, 2]


async def test_a_session_with_no_messages_counts_zero_turns_on_all_three_readers(
    client,
    db_session,
):
    team = await a_team(db_session)
    headers = await a_facilitator_of(db_session, team)
    session = await a_session(db_session, team, guide_lines=1)
    session.messages = []
    await db_session.commit()
    await keep_a_take(db_session, session, audio=b"parte 1", ordinal=1, pass_number=1)

    assert await the_three_counts(client, db_session, team, headers, session) == [0, 0, 0]
