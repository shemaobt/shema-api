"""Every moment the Desk is served says which clock it is on.

`app/utils/stored_time.py` was born with six callers and reached none of the Desk's own
routes. The three here served the column value straight off the row, so on SQLite — where
`DateTime(timezone=True)` reads back **naive** — the wire carried `2026-08-21T01:00:00` with
nothing after it.

**The edge case is the whole point, and it is not "three hours out".** A bare moment is read
as *local* by whoever receives it, and near midnight that moves the **day**. Measured for
`America/Sao_Paulo`, the clock this product runs on: an instant stored at 01:00 UTC on the
21st is 22:00 on the **20th** there. Served bare, a browser reads the digits as local time and
draws the 21st — so the facilitator sees a conversation on a day it did not happen, and no
test anywhere raises, because nothing failed.

That is why each test below asserts twice: that the offset is on the wire at all, and that
reading the served value lands on the day that actually happened.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.auth import Role
from app.db.models.internalization_room import IRSession, IRTakeKind
from app.services.internalization_room import questions as question_service
from app.services.internalization_room import takes as take_service
from tests.baker import (
    grant_facilitator_app_role,
    make_app,
    make_language,
    make_project,
    make_project_user_access,
    make_role,
    make_user,
    make_user_app_role,
)

IR = "/api/internalization-room"
APP_KEY = "internalization-room"

#: 01:00 UTC on the 21st is 22:00 on the **20th** in Sao Paulo. Served bare, the digits read
#: as local and the Desk draws the 21st — the day the conversation did not happen.
NEAR_MIDNIGHT = datetime(2026, 8, 21, 1, 0, tzinfo=UTC)
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
THE_DAY_IT_HAPPENED = 20


def day_in_sao_paulo(served: str) -> int:
    """The day a client in this product's own timezone draws from what was served."""
    return datetime.fromisoformat(served).astimezone(SAO_PAULO).day


def says_which_clock(served: str) -> bool:
    return served.endswith(("Z", "+00:00"))


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
async def room_app(db_session):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
async def room_client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
async def desk_client(db_session: AsyncSession):
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


async def a_room_facilitator(db: AsyncSession, room_app) -> tuple[dict[str, str], str]:
    """A facilitator, and the team whose work they reach.

    The team is not decoration. ENG-452 and ENG-534 scope every facilitator route to the
    caller's own teams, so a facilitator of nothing reads an empty inbox and gets a 404 for
    a session — both correct, and both hiding whatever a case here meant to assert about
    the moment on the wire.
    """
    user = await make_user(db, email="facilitador@example.com")
    role = (
        await db.execute(
            select(Role).where(Role.app_id == room_app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db, user.id, room_app.id, role.id)
    language = await make_language(db, name="Lingua da sala", code="lsl")
    project = await make_project(db, language.id, name="Equipe da sala")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    return await auth_header(db, user), project.id


async def _stored_at(db: AsyncSession, row, when: datetime | None) -> None:
    """Commit, then forget **this row** — so the next read comes back off the driver.

    Without the expiry the row keeps the **aware** value the test assigned, and every
    assertion below passes over code that normalises nothing. Measured: the takes case went
    green that way before this existed, which is the false green this helper exists to stop.

    One row and not `expire_all`, because expiring the whole identity map strands every other
    object the test is still holding — reading an id off one of them then attempts IO outside
    the async context and raises `MissingGreenlet`.
    """
    if when is not None:
        row.created_at = when
    await db.commit()
    db.expire(row)


async def test_the_inbox_says_when_the_hand_went_up(room_client, db_session, room_app):
    """`asked_at` is what orders the facilitator's queue and what dates each card."""
    headers, team = await a_room_facilitator(db_session, room_app)
    session = IRSession(id="sessao-da-pergunta", pericope="P03", project_id=team)
    db_session.add(session)
    await db_session.commit()
    question = await question_service.raise_question(
        db_session,
        device_id="tablet-1",
        session_id=session.id,
        pericope="P03",
        audio=b"a equipe perguntou",
        project_id=team,
        store=_MemoryStore(),
    )
    await _stored_at(db_session, question, NEAR_MIDNIGHT)

    answer = await room_client.get(f"{IR}/facilitator/questions", headers=headers)

    assert answer.status_code == 200, answer.text
    [asked] = [q["asked_at"] for q in answer.json()["questions"]]
    assert says_which_clock(asked), f"asked_at went out as {asked!r}, which names no clock"
    assert day_in_sao_paulo(asked) == THE_DAY_IT_HAPPENED


async def test_a_take_says_when_it_was_recorded(room_client, db_session, room_app):
    headers, team = await a_room_facilitator(db_session, room_app)
    session = IRSession(id="sessao-do-fuso", pericope="P03", project_id=team)
    db_session.add(session)
    await db_session.commit()
    take = await take_service.store_take(
        db_session,
        session_id=session.id,
        device_id="tablet-1",
        pericope=session.pericope,
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        audio=b"a equipe contou a passagem",
        store=_MemoryStore(),
    )
    await _stored_at(db_session, take, NEAR_MIDNIGHT)

    answer = await room_client.get(f"{IR}/facilitator/sessions/{session.id}/takes", headers=headers)

    assert answer.status_code == 200, answer.text
    [recorded] = [t["recorded_at"] for t in answer.json()["takes"]]
    assert says_which_clock(recorded), f"recorded_at went out as {recorded!r}, which names no clock"
    assert day_in_sao_paulo(recorded) == THE_DAY_IT_HAPPENED


async def test_a_device_row_says_when_it_was_linked_and_last_seen(desk_client, db_session):
    """Both moments on the devices panel, and `last_seen_at` is the one a facilitator reads."""
    from app.db.models.device import Device
    from app.services.device import create_device

    user = await make_user(db_session, email="facilitador@example.com")
    language = await make_language(db_session, name="Lingua", code="lin")
    project = await make_project(db_session, language.id, name="Equipe")
    await make_project_user_access(db_session, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db_session, user.id)
    minted = await create_device(db_session)
    device = (
        await db_session.execute(select(Device).where(Device.id == minted.device.id))
    ).scalar_one()
    device.project_id = project.id
    device.claimed_at = NEAR_MIDNIGHT
    device.last_seen_at = NEAR_MIDNIGHT + timedelta(minutes=5)
    await _stored_at(db_session, device, None)

    answer = await desk_client.get(
        f"/api/facilitator/teams/{project.id}/devices",
        headers=await auth_header(db_session, user),
    )

    assert answer.status_code == 200, answer.text
    [row] = answer.json()
    for field in ("linked_at", "last_seen_at"):
        served = row[field]
        assert says_which_clock(served), f"{field} went out as {served!r}, which names no clock"
        assert day_in_sao_paulo(served) == THE_DAY_IT_HAPPENED


class _MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str):
        return None
