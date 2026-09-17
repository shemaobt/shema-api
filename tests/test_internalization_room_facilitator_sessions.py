"""A room that halted for a person can be found by one.

`NEEDS_PERSON` had a writer and no reader anywhere a facilitator could reach: the two
session-scoped facilitator routes are addressed by an id, and nothing in the system ever
handed a facilitator an id. A hard stop that nobody can be told about does not stop
anything.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import Role
from app.db.models.internalization_room import IRSessionStatus, IRTakeKind
from app.services.internalization_room import questions as question_service
from app.services.internalization_room import sessions as session_service
from app.services.internalization_room import takes as take_service
from app.services.platform.storage import StoredObject
from tests.baker import make_app, make_role, make_user, make_user_app_role

APP_KEY = "internalization-room"
IR = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        checksum = Checksum()
        checksum.update(stored)
        return StoredObject(
            size=len(stored), crc32c=base64.b64encode(checksum.digest()).decode("ascii")
        )


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router as room_router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


#: A team is a project — the same thing in this system — so the sessions this listing
#: answers for are the ones whose `project_id` is a project the caller facilitates.
_TEAM = "Equipe da sala"


async def _team(db_session: AsyncSession, name: str = _TEAM):
    """The team these sessions belong to, made once and found again by name."""
    from app.db.models.project import Project
    from tests.baker import make_language, make_project

    found = (
        await db_session.execute(select(Project).where(Project.name == name))
    ).scalar_one_or_none()
    if found is not None:
        return found
    language = await make_language(db_session, name=f"Lingua {name}", code=name[-3:].lower())
    return await make_project(db_session, language.id, name=name)


async def _a_session(db_session: AsyncSession, *, team=None, pericope: str = "P03"):
    """A conversation belonging to a team, because one belonging to nobody reaches nobody."""
    team = team or await _team(db_session)
    return await session_service.create_session(db_session, pericope=pericope, project_id=team.id)


async def _facilitator(db_session: AsyncSession, room_app, team=None) -> dict[str, str]:
    from app.core.enums import ProjectRole
    from app.services.auth.issue_tokens import issue_tokens
    from tests.baker import make_project_user_access

    user = await make_user(db_session)
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == room_app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db_session, user.id, room_app.id, role.id)
    team = team or await _team(db_session)
    await make_project_user_access(db_session, team.id, user.id, role=ProjectRole.FACILITATOR)
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def _record_a_take(db_session: AsyncSession, session):
    return await take_service.store_take(
        db_session,
        session_id=session.id,
        device_id="tablet-1",
        pericope=session.pericope,
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        audio=b"a equipe contou a passagem inteira",
        store=MemoryStore(),
    )


async def _halt(client: httpx.AsyncClient, session_id: str) -> None:
    """The way the room actually halts: the tablet says it cannot go on without a person."""
    asked = await client.post(
        f"{IR}/sessions/{session_id}/needs-person", headers={"X-Room-Key": ROOM_KEY}
    )
    assert asked.status_code == 200, asked.text[:200]


@pytest.mark.asyncio
async def test_a_room_that_halted_for_a_person_is_visible_to_one(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    session = await _a_session(db_session)
    await _halt(client, session.id)

    listed = await client.get(
        f"{IR}/facilitator/sessions", headers=await _facilitator(db_session, room_app)
    )

    assert listed.status_code == 200, listed.text[:300]
    halted = [row for row in listed.json()["sessions"] if row["session_id"] == session.id]
    assert halted, "a sala parou pedindo uma pessoa e nenhuma consegue saber disso"
    assert halted[0]["status"] == IRSessionStatus.NEEDS_PERSON.value


@pytest.mark.asyncio
async def test_the_id_the_listing_gives_opens_the_door_it_addresses(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """A listing whose ids do not work anywhere has moved the problem, not closed it."""
    session = await _a_session(db_session)
    take = await _record_a_take(db_session, session)
    await _halt(client, session.id)
    headers = await _facilitator(db_session, room_app)

    listed = await client.get(f"{IR}/facilitator/sessions", headers=headers)
    found = next(row for row in listed.json()["sessions"] if row["session_id"] == session.id)
    recorded = await client.get(
        f"{IR}/facilitator/sessions/{found['session_id']}/takes", headers=headers
    )

    assert recorded.status_code == 200, recorded.text[:300]
    assert [t["take_id"] for t in recorded.json()["takes"]] == [take.id]


@pytest.mark.asyncio
async def test_an_open_question_leads_to_the_session_it_came_from(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    session = await _a_session(db_session)
    take = await _record_a_take(db_session, session)
    await question_service.raise_question(
        db_session,
        device_id="tablet-1",
        session_id=session.id,
        pericope=session.pericope,
        project_id=session.project_id,
        audio=b"a equipe perguntou",
        store=MemoryStore(),
    )
    headers = await _facilitator(db_session, room_app)

    waiting = await client.get(f"{IR}/facilitator/questions", headers=headers)
    asked_in = waiting.json()["questions"][0]["session_id"]
    recorded = await client.get(f"{IR}/facilitator/sessions/{asked_in}/takes", headers=headers)

    assert recorded.status_code == 200, recorded.text[:300]
    assert [t["take_id"] for t in recorded.json()["takes"]] == [take.id], (
        "a pergunta precisa levar à sessão de que veio, não a outra qualquer"
    )


@pytest.mark.asyncio
async def test_a_session_still_under_way_is_not_in_the_listing(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """The list is a queue of what waits on a person, not a dump of every session."""
    under_way = await _a_session(db_session)
    halted = await _a_session(db_session)
    await _halt(client, halted.id)
    finished = await _a_session(db_session)
    finished.status = IRSessionStatus.DONE
    await db_session.commit()

    listed = await client.get(
        f"{IR}/facilitator/sessions", headers=await _facilitator(db_session, room_app)
    )

    shown = {row["session_id"] for row in listed.json()["sessions"]}
    assert halted.id in shown and finished.id in shown
    assert under_way.id not in shown


@pytest.mark.asyncio
async def test_the_most_recent_session_is_at_the_front(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """A queue that does not put the newest first is not a queue."""
    older = await _a_session(db_session)
    newer = await _a_session(db_session)
    await _halt(client, older.id)
    await _halt(client, newer.id)
    moment = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    older.updated_at = moment - timedelta(hours=1)
    newer.updated_at = moment
    await db_session.commit()

    listed = await client.get(
        f"{IR}/facilitator/sessions", headers=await _facilitator(db_session, room_app)
    )

    order = [row["session_id"] for row in listed.json()["sessions"]]
    assert order.index(newer.id) < order.index(older.id)


@pytest.mark.asyncio
async def test_without_a_login_the_listing_does_not_answer(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    session = await _a_session(db_session)
    await _halt(client, session.id)

    assert (await client.get(f"{IR}/facilitator/sessions")).status_code == 401


@pytest.mark.asyncio
async def test_the_room_key_does_not_open_the_facilitator_listing(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """The key is the same on every tablet — it identifies the app, not a person."""
    session = await _a_session(db_session)
    await _halt(client, session.id)

    listed = await client.get(f"{IR}/facilitator/sessions", headers={"X-Room-Key": ROOM_KEY})

    assert listed.status_code == 401


@pytest.mark.asyncio
async def test_a_facilitator_of_another_team_does_not_see_the_halted_room(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """The case without which this route works and answers too much.

    Nothing goes red when a listing is unscoped: it returns 200 and the body has content.
    The only case that tells a scoped listing from an unscoped one is the caller who should
    not be in it — everything else passes either way.

    What leaks without it is not the recording. It is that another team stopped and asked
    for help, on which passage, and when — handed over as ids that this reader is then
    refused at `…/{id}/takes` and `…/{id}/release`, both of which scope by team.
    """
    theirs = await _team(db_session, name="Equipe de outra gente")
    session = await _a_session(db_session, team=theirs)
    await _halt(client, session.id)

    outsider = await _facilitator(db_session, room_app)

    listed = await client.get(f"{IR}/facilitator/sessions", headers=outsider)

    assert listed.status_code == 200, listed.text[:300]
    seen = [row["session_id"] for row in listed.json()["sessions"]]
    assert session.id not in seen, (
        f"a sessao de outra equipe apareceu na listagem de quem nao a facilita: {seen}"
    )


@pytest.mark.asyncio
async def test_the_facilitator_of_the_team_still_sees_it(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """The other half, and the one that keeps the case above from being satisfied by a bug.

    A filter that returns nothing to everybody passes the case above and is just as wrong.
    Scoping too tightly is the easy mistake to make with a new restriction, and this is the
    assertion that refuses it.
    """
    theirs = await _team(db_session, name="Equipe de outra gente")
    session = await _a_session(db_session, team=theirs)
    await _halt(client, session.id)

    insider = await _facilitator(db_session, room_app, team=theirs)

    listed = await client.get(f"{IR}/facilitator/sessions", headers=insider)

    assert listed.status_code == 200, listed.text[:300]
    seen = [row["session_id"] for row in listed.json()["sessions"]]
    assert session.id in seen, (
        "quem facilita a equipe deixou de ver a propria sala parada — o filtro aperta demais"
    )
