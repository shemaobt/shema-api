"""The panorama plays once per book, and a team can ask to hear it again.

The app's automatic launch request is still answered with the passage the team stands on
once the book's panorama has been heard. A request the team chose — the spoke on the wheel,
under a member who joined late or a team that forgot the shape of the book — is honoured and
opens a panorama session, heard or not. The difference travels on the request and nowhere
else: `heard_panorama` stays derived from the rows, and nothing is stored to say "asked".

A second panorama is a fresh conversation, as her design reopens it from zero. It is not
about to hand the team into a passage, so the opening `prepare_opening` writes ahead for a
first panorama is not written for it.
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
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import make_language, make_project, make_project_user_access, make_user

_codes = itertools.count(60)
PREFIX = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"
THE_PANORAMA_LINE = "Vamos conhecer o livro de Rute de novo."


async def a_team(db: AsyncSession, *, name: str):
    language = await make_language(db, name=name, code=f"w{next(_codes):02d}")
    return await make_project(db, language.id, name=name)


async def having_heard_the_panorama(db: AsyncSession, team) -> None:
    launched = await room.create_session(db, pericope="OV", project_id=team.id)
    assert room.is_panorama(launched.pericope)
    await room.create_session(db, after_panorama=True, project_id=team.id)


@pytest.mark.asyncio
async def test_a_team_that_asks_for_the_panorama_hears_it_even_after_the_book_was_heard(
    db_session: AsyncSession,
) -> None:
    """The launch relands on the passage; the team's own request opens the panorama, and
    not as a session that follows one — none did, this *is* one."""
    team = await a_team(db_session, name="Pede de novo")
    await having_heard_the_panorama(db_session, team)

    relaunched = await room.create_session(db_session, pericope="OV", project_id=team.id)
    asked = await room.create_session(db_session, pericope="OV", project_id=team.id, chosen=True)

    assert not room.is_panorama(relaunched.pericope)
    assert room.is_panorama(asked.pericope)
    assert asked.after_panorama is False


# ------------------------------------------------------------------- over HTTP, as the app does


@pytest.fixture()
def prepared() -> list[str]:
    """Which sessions the route asked to have an opening written ahead for."""
    return []


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, prepared: list[str]):
    """The room over HTTP, with the panorama's model and voice stood in for: what the
    Guide says is not the question here, only that a chosen panorama is opened and spoken.
    The background preparation is stood in for too, and only its being asked is kept."""
    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    async def _panorama(**_: Any) -> TurnOutcome:
        return TurnOutcome(
            speech=THE_PANORAMA_LINE,
            transcript="",
            peer_cue=False,
            redrafts=0,
            issues=[],
            used_fail_safe=False,
        )

    async def _speech(text: str, **_: object) -> tuple[SynthesizedSpeech, bool]:
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/v/m/f/{abs(hash(text))}.mp3",
        )
        return entry, False

    async def _remember(session_id: str, *_: Any, **__: Any) -> None:
        prepared.append(session_id)

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
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


async def the_room_opens(client, headers: dict[str, str], session_id: str) -> dict[str, Any]:
    spoken = await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers=headers)
    assert spoken.status_code == 200, spoken.text[:200]
    return spoken.json()


@pytest.mark.asyncio
async def test_over_http_a_chosen_panorama_opens_and_the_room_speaks_it(
    client, db_session: AsyncSession
) -> None:
    """The ticket's own test, as the tablet lives it: the launch after the book was heard
    lands on the passage; the same tablet asking with `chosen` is handed a panorama session
    and the opening turn comes back with a clip to play."""
    team = await a_team(db_session, name="Pelo aparelho, de novo")
    tablet = await a_tablet_of(db_session, team)
    launched = await the_app_posts(client, tablet, {"pericope": "OV"})
    await the_app_posts(client, tablet, {"after_session": launched["session_id"]})

    relaunched = await the_app_posts(client, tablet, {"pericope": "OV"})
    asked = await the_app_posts(client, tablet, {"pericope": "OV", "chosen": True})

    assert not room.is_panorama(relaunched["pericope"])
    assert room.is_panorama(asked["pericope"])
    assert asked["session_id"] != launched["session_id"]
    opening = await the_room_opens(client, tablet, asked["session_id"])
    assert opening["audio_url"].startswith(f"{PREFIX}/voice/")


@pytest.mark.asyncio
async def test_a_second_panorama_spends_no_prepared_opening(
    client, db_session: AsyncSession, prepared: list[str]
) -> None:
    """The first panorama writes the passage's opening ahead, because the team is about to
    enter it. A team already inside the book asking to hear the panorama again is not
    about to enter anything, so no opening is written for it to discard."""
    team = await a_team(db_session, name="Sem abertura à toa")
    tablet = await a_tablet_of(db_session, team)
    launched = await the_app_posts(client, tablet, {"pericope": "OV"})
    await the_app_posts(client, tablet, {"after_session": launched["session_id"]})

    asked = await the_app_posts(client, tablet, {"pericope": "OV", "chosen": True})

    assert room.is_panorama(asked["pericope"])
    assert prepared == [launched["session_id"]]
