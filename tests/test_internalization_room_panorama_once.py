"""ENG-453 — the panorama is the book's, and its opening is written ahead once.

Since ENG-1237 the open door never redirects: a request for the panorama opens the team's
panorama session, heard or not (ADR 0045), and a named passage opens that passage. What
`heard_panorama` still decides is whether the route writes an opening ahead for a panorama
it just created, which only a team about to enter the book needs.

"Heard" is decided from what the room already writes. A panorama session carries the book
and not the passage, so it cannot key anything on a pericope by itself; the session the
wooden bead opens after it carries both — `after_panorama=True` on the passage the team
entered. That is the record a wordless room leaves of a team having heard it and gone on.
"""

from __future__ import annotations

import itertools
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import router as room_router
from app.api.internalization_room import sessions as sessions_api
from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.config import get_settings
from app.core.database import get_db
from app.core.enums import ProjectRole
from app.core.exceptions import register_exception_handlers
from app.services.device import claim_device_as_facilitator, create_device
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from tests.baker import (
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

_codes = itertools.count(40)
PREFIX = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]
FIRST = CANON[0]


async def a_team(db: AsyncSession, *, name: str):
    language = await make_language(db, name=name, code=f"v{next(_codes):02d}")
    return await make_project(db, language.id, name=name)


async def the_app_launches(db: AsyncSession, team):
    """The app asks for the panorama at launch."""
    return await room.create_session(db, pericope="OV", project_id=team.id)


async def the_bead_opens_the_passage(db: AsyncSession, team):
    """After the panorama has been spoken the wooden bead opens the passage — the app names
    no passage and says which session it comes after, which the route maps to this flag."""
    return await room.create_session(db, after_panorama=True, project_id=team.id)


async def having_heard_the_panorama(db: AsyncSession, team) -> None:
    launched = await the_app_launches(db, team)
    assert room.is_panorama(launched.pericope)
    await the_bead_opens_the_passage(db, team)


async def test_naming_a_passage_or_none_resolves_as_before_once_the_panorama_was_heard(
    db_session: AsyncSession,
) -> None:
    """A team that heard the panorama is opened the passage it names, or the passage it
    stands on when it names none, with the mark it asked for."""
    team = await a_team(db_session, name="Escolhe")
    await having_heard_the_panorama(db_session, team)

    silent = await room.create_session(db_session, project_id=team.id)
    named = await room.create_session(db_session, pericope=CANON[4], project_id=team.id)
    named_after = await room.create_session(
        db_session, pericope=CANON[4], after_panorama=True, project_id=team.id
    )

    assert silent.pericope == FIRST
    assert named.pericope == CANON[4]
    assert named_after.after_panorama is True


# ------------------------------------------------------------------- over HTTP, as the app does


@pytest.fixture()
def prepared() -> list[str]:
    """Which sessions the route asked to have an opening written ahead for."""
    return []


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, prepared: list[str]):
    """The room over HTTP. The panorama's background preparation is stood in for: it
    writes ahead with a model, and nothing here is about what it writes, only whether it
    was asked to."""
    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    async def _remember(session_id: str, *_: Any, **__: Any) -> None:
        prepared.append(session_id)

    monkeypatch.setattr(sessions_api, "prepare_opening", _remember)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c


async def a_tablet_of(db: AsyncSession, team) -> dict[str, str]:
    """The headers of a device a facilitator claimed for this team."""
    user = await make_user(db, email=f"fac-{team.id[:8]}@example.com")
    await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=user, code=minted.claim_code, project_id=team.id
    )
    return {"X-Room-Key": ROOM_KEY, DEVICE_CREDENTIAL_HEADER: claimed.credential}


async def the_app_posts(client, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    created = await client.post(f"{PREFIX}/sessions", headers=headers, json=body)
    assert created.status_code == 200, created.text[:200]
    return created.json()


async def test_a_team_already_inside_the_book_is_written_no_opening_for_a_new_panorama(
    client, db_session: AsyncSession, prepared: list[str]
) -> None:
    """The first panorama writes the passage's opening ahead, because the team is about to
    enter it. A team that heard it and went on, opening a panorama of its own again in another
    language, is there for the book's shape, so no opening is written for it."""
    team = await a_team(db_session, name="Sem abertura à toa")
    tablet = await a_tablet_of(db_session, team)
    launched = await the_app_posts(client, tablet, {"pericope": "OV"})
    await the_app_posts(client, tablet, {"after_session": launched["session_id"]})

    again = await the_app_posts(client, tablet, {"pericope": "OV", "language": "pt"})

    assert room.is_panorama(again["pericope"])
    assert again["session_id"] != launched["session_id"]
    assert prepared == [launched["session_id"]]


async def test_another_teams_hearing_does_not_count_for_this_one(
    client, db_session: AsyncSession, prepared: list[str]
) -> None:
    """The key is the team's: two teams in the same installation each have it written."""
    heard = await a_tablet_of(db_session, await a_team(db_session, name="Ouviu"))
    fresh = await a_tablet_of(db_session, await a_team(db_session, name="Nunca ouviu"))
    launched = await the_app_posts(client, heard, {"pericope": "OV"})
    await the_app_posts(client, heard, {"after_session": launched["session_id"]})

    first = await the_app_posts(client, fresh, {"pericope": "OV"})

    assert prepared == [launched["session_id"], first["session_id"]]


async def test_a_panorama_opened_but_never_followed_into_the_passage_is_not_heard(
    client, db_session: AsyncSession, prepared: list[str]
) -> None:
    """A panorama session opened and abandoned is a request, not a hearing: the team's next
    new panorama still has its opening written ahead."""
    tablet = await a_tablet_of(db_session, await a_team(db_session, name="Caiu no meio"))
    abandoned = await the_app_posts(client, tablet, {"pericope": "OV"})

    again = await the_app_posts(client, tablet, {"pericope": "OV", "language": "pt"})

    assert prepared == [abandoned["session_id"], again["session_id"]]


async def test_a_tablet_that_never_said_whose_it_is_has_every_opening_written(
    client, prepared: list[str]
) -> None:
    """No team, no history: nothing can have been heard."""
    shared = {"X-Room-Key": ROOM_KEY}
    launched = await the_app_posts(client, shared, {"pericope": "OV"})
    await the_app_posts(client, shared, {"after_session": launched["session_id"]})

    again = await the_app_posts(client, shared, {"pericope": "OV"})

    assert prepared == [launched["session_id"], again["session_id"]]
