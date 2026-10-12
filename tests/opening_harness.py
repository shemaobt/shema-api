"""What a case about opening a session needs: a scripted room, a team's tablets and the Desk.

The room's voice, transcriber and synthesizer stood in for by a script a case can steer, the
tablet's own calls on the open door and the turn route, and the Desk's team routes over the
case's database. Shared by the open-door cases and the Zerar cases; each module keeps its own
three-line fixtures calling these.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastapi import APIRouter
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import ProjectRole
from app.db.models.project import Project
from app.services.internalization_room.hearing import HeardSpeech
from tests.baker import make_project_user_access, make_user
from tests.device_harness import a_linked_tablet
from tests.release_harness import PREFIX, team_headers
from tests.tablet_turn_harness import the_team_says as a_turn_is_said
from tests.tablet_turn_harness import the_turn_is_scripted

GUIDE_OPENING = "Vamos ouvir a historia de Rute. O que voces ja sabem dela?"
GUIDE_LINE = "Vamos ficar nesta cena. O que voces contariam?"
NOTE_PT_P01 = (
    "[A sessão acabou de começar. A equipe abriu a passagem P01 e está à mesa, pronta para "
    "começar. Fale primeiro.]"
)
NOTE_PT_P03 = (
    "[A sessão acabou de começar. A equipe abriu a passagem P03 e está à mesa, pronta para "
    "começar. Fale primeiro.]"
)
NOTE_PT_OV_RUTH = (
    "[A sessão acabou de começar. A equipe abriu o Panorama do Livro de Ruth e está à mesa, "
    "pronta para conversar. Fale primeiro.]"
)


async def ask_for_the_opening(
    client: httpx.AsyncClient, session_id: str, turn_id: str | None = "abertura"
) -> httpx.Response:
    """A turn with no recording, under `turn_id` or under none."""
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        data={"turn_id": turn_id} if turn_id else {},
    )


class Script:
    """What the team says next; the room opens while it has said nothing.

    `meanwhile` runs once, while the voice is thinking: after the turn resolved its session
    and before it lands, which is where a request racing the turn falls in the field.
    """

    def __init__(self) -> None:
        self.said = ""
        self.meanwhile: Callable[[], Awaitable[None]] | None = None


def a_scripted_room(monkeypatch: pytest.MonkeyPatch) -> Script:
    scripted = Script()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text=scripted.said)

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        if scripted.meanwhile is not None:
            racing, scripted.meanwhile = scripted.meanwhile, None
            await racing()
        return GUIDE_OPENING if not scripted.said else GUIDE_LINE

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    return scripted


async def another_tablet_of(db: AsyncSession, team: Project) -> str:
    """A tablet a facilitator of this team claimed, and the credential it calls with."""
    user = await make_user(db, email=f"fac-{uuid.uuid4()}@example.com")
    await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    return (await a_linked_tablet(db, team_id=team.id, facilitator=user)).credential


async def the_tablet_opens(
    client: httpx.AsyncClient, credential: str, body: dict[str, Any]
) -> dict[str, Any]:
    opened = await client.post(f"{PREFIX}/sessions", headers=team_headers(credential), json=body)
    assert opened.status_code == 200, opened.text[:300]
    return opened.json()


async def the_team_speaks(
    client: httpx.AsyncClient, script: Script, credential: str, session_id: str, said: str
) -> httpx.Response:
    script.said = said
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=team_headers(credential),
        data={"turn_id": str(uuid.uuid4())},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def the_team_says(
    client: httpx.AsyncClient, script: Script, credential: str, session_id: str, said: str
) -> None:
    script.said = said
    await a_turn_is_said(client, credential, session_id, str(uuid.uuid4()))


@asynccontextmanager
async def _desk_router_on_an_app(
    router: APIRouter,
    prefix: str,
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession] | None,
) -> AsyncIterator[httpx.AsyncClient]:
    from fastapi import FastAPI

    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(router, prefix=prefix)
    register_exception_handlers(test_app)

    async def _get_db():
        if per_request is None:
            yield db_session
            return
        async with per_request() as session:
            yield session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client


@asynccontextmanager
async def desk_routes(
    db_session: AsyncSession, *, per_request: async_sessionmaker[AsyncSession] | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    """The Desk's team routes on an app of their own, over the case's database.

    `per_request` gives every request a session of its own, as `room_client` does.
    """
    from app.api.facilitator.teams import facilitator_teams_router

    async with _desk_router_on_an_app(
        facilitator_teams_router, "/api/facilitator/teams", db_session, per_request
    ) as client:
        yield client


@asynccontextmanager
async def desk_sessions_routes(
    db_session: AsyncSession, *, per_request: async_sessionmaker[AsyncSession] | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    """The Desk's sessions tile on an app of their own, over the case's database."""
    from app.api.facilitator.sessions import facilitator_sessions_router

    async with _desk_router_on_an_app(
        facilitator_sessions_router, "/api/facilitator/sessions", db_session, per_request
    ) as client:
        yield client
