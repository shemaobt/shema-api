"""ENG-453 — the panorama plays once per book, not once per launch.

The app asks for `"OV"` at every launch and the room honoured it every time, so a team
reopening the tablet on the passage they were already working heard the book's panorama
again before reaching their own passage. The decision now lives where the request lands:
a panorama the team has already heard for the book is answered with the passage they stand
on instead.

None of these assert on storage. They look at the session the room hands back — which
passage, and whether it is a panorama — the same thing the tablet reads. The one exception is
the `after_panorama` flag, which is the greeting's input (`live_turn` speaks "we just walked the
panorama together" off it) and the only way to see, without an LLM, whether the room claims
a meeting that did not happen.

"Heard" is decided from what the room already writes. A panorama session carries the book
and not the passage, so it cannot key anything on a pericope by itself; the session the
wooden bead opens after it carries both — `after_panorama=True` on the passage the team
entered. That is the record a wordless room leaves of a team having heard it and gone on.

ENG-769 — and a team can ask to hear it again. The launch's request is still answered with
the passage once the book has been heard; a request the team chose — the spoke on the wheel —
is honoured and opens a panorama session, heard or not, as a fresh conversation. The
difference travels on the request, nothing is stored to say "asked", and the opening
`prepare_opening` writes ahead for a first panorama is not written for a second one.
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
from app.services.internalization_room.canon.book_material import unwalkable
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import (
    having_finished_the_passage,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    open_ir_session,
)

_codes = itertools.count(40)
PREFIX = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"
THE_PANORAMA_LINE = "Vamos conhecer o livro de Rute de novo."

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]
FIRST, SECOND = CANON[0], CANON[1]
WALKABLE = [
    meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK) if not unwalkable(meaning_map)
]


async def a_team(db: AsyncSession, *, name: str):
    language = await make_language(db, name=name, code=f"v{next(_codes):02d}")
    return await make_project(db, language.id, name=name)


async def having_closed(db: AsyncSession, team, *pericopes: str) -> None:
    """Worked to the floor and then recorded, which is what finishes a passage."""
    for pericope in pericopes:
        session = await open_ir_session(db, pericope=pericope, project_id=team.id)
        await having_finished_the_passage(db, session)


async def the_app_launches(db: AsyncSession, team):
    """Every launch asks for the panorama; which session comes back is the room's to say."""
    return await room.create_session(db, pericope="OV", project_id=team.id)


async def the_bead_opens_the_passage(db: AsyncSession, team):
    """After the panorama has been spoken the wooden bead opens the passage — the app names
    no passage and says which session it comes after, which the route maps to this flag."""
    return await room.create_session(db, after_panorama=True, project_id=team.id)


async def having_heard_the_panorama(db: AsyncSession, team) -> None:
    launched = await the_app_launches(db, team)
    assert room.is_panorama(launched.pericope)
    await the_bead_opens_the_passage(db, team)


# ------------------------------------------------------------------------------ the defect


@pytest.mark.asyncio
async def test_a_team_that_heard_the_panorama_for_this_passage_is_not_played_it_again(
    db_session: AsyncSession,
) -> None:
    """Case 1. The reopen lands on the passage the team is on, not on a second panorama."""
    team = await a_team(db_session, name="Já ouviu")
    await having_heard_the_panorama(db_session, team)

    reopened = await the_app_launches(db_session, team)

    assert not room.is_panorama(reopened.pericope)
    assert reopened.pericope == FIRST


@pytest.mark.asyncio
async def test_a_team_reaching_a_new_passage_is_not_played_the_book_again(
    db_session: AsyncSession,
) -> None:
    """Case 2. Per book: the panorama is the book's, so a team that went on from it into the
    first passage and finished that passage arrives at the second without sitting through
    the whole of Ruth again. The session handed back is the only one minted, so a launch
    answered with the passage is a launch that minted no panorama."""
    team = await a_team(db_session, name="Chegou na segunda")
    await having_heard_the_panorama(db_session, team)
    await having_closed(db_session, team, FIRST)

    arriving = await the_app_launches(db_session, team)

    assert not room.is_panorama(arriving.pericope)
    assert arriving.pericope == SECOND


@pytest.mark.asyncio
async def test_another_teams_hearing_does_not_count_for_this_one(
    db_session: AsyncSession,
) -> None:
    """The key is the team's: two teams in the same installation each hear it."""
    heard = await a_team(db_session, name="Ouviu")
    fresh = await a_team(db_session, name="Nunca ouviu")
    await having_heard_the_panorama(db_session, heard)

    launched = await the_app_launches(db_session, fresh)

    assert room.is_panorama(launched.pericope)


@pytest.mark.asyncio
async def test_a_passage_opened_in_place_of_the_panorama_does_not_claim_the_meeting(
    db_session: AsyncSession,
) -> None:
    """The greeting follows `after_panorama`: "we just walked the panorama together". A
    request that says it comes after a panorama is answered with the passage, and the
    passage must not greet the team as if a panorama had just played — none did."""
    team = await a_team(db_session, name="Sem encontro")
    await having_heard_the_panorama(db_session, team)

    reopened = await room.create_session(
        db_session, pericope="OV", after_panorama=True, project_id=team.id
    )

    assert not room.is_panorama(reopened.pericope)
    assert reopened.after_panorama is False


@pytest.mark.asyncio
async def test_a_team_that_asks_for_the_panorama_hears_it_even_after_the_book_was_heard(
    db_session: AsyncSession,
) -> None:
    """The launch relands on the passage; the team's own request opens the panorama, and
    not as a session that follows one — none did, this *is* one."""
    team = await a_team(db_session, name="Pede de novo")
    await having_heard_the_panorama(db_session, team)

    relaunched = await the_app_launches(db_session, team)
    asked = await room.create_session(db_session, pericope="OV", project_id=team.id, chosen=True)

    assert not room.is_panorama(relaunched.pericope)
    assert room.is_panorama(asked.pericope)
    assert asked.after_panorama is False


# ------------------------------------------------------------------------------ controls


@pytest.mark.asyncio
async def test_a_team_that_never_heard_the_panorama_hears_it(db_session: AsyncSession) -> None:
    """Case 3. First launch ever."""
    team = await a_team(db_session, name="Primeira vez")

    launched = await the_app_launches(db_session, team)

    assert room.is_panorama(launched.pericope)


@pytest.mark.asyncio
async def test_a_panorama_opened_but_never_followed_into_the_passage_is_played_again(
    db_session: AsyncSession,
) -> None:
    """A panorama session that was opened and abandoned — the app crashed, the audio never
    came — is a request, not a hearing. What a wordless room can know about a team having
    heard the panorama is that they went on from it, and that is the record it reads."""
    team = await a_team(db_session, name="Caiu no meio")
    await the_app_launches(db_session, team)

    launched = await the_app_launches(db_session, team)

    assert room.is_panorama(launched.pericope)


@pytest.mark.asyncio
async def test_a_tablet_that_never_said_whose_it_is_always_hears_the_panorama(
    db_session: AsyncSession,
) -> None:
    """No team, no history: nothing can have been heard, so nothing is skipped."""
    await room.create_session(db_session, pericope="OV", project_id=None)
    await room.create_session(db_session, after_panorama=True, project_id=None)

    launched = await room.create_session(db_session, pericope="OV", project_id=None)

    assert room.is_panorama(launched.pericope)


@pytest.mark.asyncio
async def test_a_team_with_nothing_left_to_walk_is_still_given_the_panorama(
    db_session: AsyncSession,
) -> None:
    """The decision replaces the panorama with the passage the team stands on. A team that
    has closed every passage the book can walk stands on none, so there is nothing to put
    in its place and the request is honoured as it always was — not refused."""
    team = await a_team(db_session, name="Andou tudo")
    await having_heard_the_panorama(db_session, team)
    await having_closed(db_session, team, *WALKABLE)

    launched = await the_app_launches(db_session, team)

    assert room.is_panorama(launched.pericope)


@pytest.mark.asyncio
async def test_naming_a_passage_or_none_resolves_as_before_once_the_panorama_was_heard(
    db_session: AsyncSession,
) -> None:
    """Case 4. Only the `"OV"` request is decided; every other request is untouched."""
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
    """The room over HTTP. The panorama's background preparation is stood in for — it
    writes ahead with a model, and nothing here is about what it writes, only whether it
    was asked to — and so are the panorama's model and voice: what the Guide says is not
    the question, only that a chosen panorama is opened and spoken."""
    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    async def _remember(session_id: str, *_: Any, **__: Any) -> None:
        prepared.append(session_id)

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

    monkeypatch.setattr(sessions_api, "prepare_opening", _remember)
    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)

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
async def test_over_http_the_relaunch_lands_on_the_passage_the_bead_opened(
    client, db_session: AsyncSession
) -> None:
    """Case 1 as the tablet lives it: launch asks `OV`, the bead says which session it comes
    after and names no passage, the relaunch asks `OV` again — and reads the passage it is
    handed, which is what #106 on the app does with the answer."""
    team = await a_team(db_session, name="Pelo aparelho")
    tablet = await a_tablet_of(db_session, team)

    launched = await the_app_posts(client, tablet, {"pericope": "OV"})
    assert room.is_panorama(launched["pericope"])
    entered = await the_app_posts(client, tablet, {"after_session": launched["session_id"]})
    assert entered["pericope"] == FIRST

    relaunched = await the_app_posts(client, tablet, {"pericope": "OV"})

    assert not room.is_panorama(relaunched["pericope"])
    assert relaunched["pericope"] == FIRST


@pytest.mark.asyncio
async def test_over_http_a_chosen_panorama_opens_and_the_room_speaks_it(
    client, db_session: AsyncSession
) -> None:
    """ENG-769's own test, as the tablet lives it: the launch after the book was heard
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
    enter it. A team already inside the book asking to hear the panorama again is there for
    the book's shape, so no opening is written for it."""
    team = await a_team(db_session, name="Sem abertura à toa")
    tablet = await a_tablet_of(db_session, team)
    launched = await the_app_posts(client, tablet, {"pericope": "OV"})
    await the_app_posts(client, tablet, {"after_session": launched["session_id"]})

    asked = await the_app_posts(client, tablet, {"pericope": "OV", "chosen": True})

    assert room.is_panorama(asked["pericope"])
    assert prepared == [launched["session_id"]]
