"""ENG-1294 — the Wheel says which passages the team has a live Release of.

The app draws its approved mark from `approved` on each entry of
`GET /books/{book}/passages`, never from what one tablet remembers. A passage is approved
while the team's draft of it stands under its latest live Release, approved from any tablet,
forced or not (ADR 0081); a re-open takes the mark away until the next approval, and a Zerar
archives the release and the mark goes with it. A passage rehearsed, talked in or never opened
is not.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.db.models.internalization_room import IRSession
from app.db.models.project import Project
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.segments import final_segments
from tests.baker import make_app, make_role
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import (
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    claimed_tablets_of_one_team,
    desk_release,
    ready_session,
    rehearsed_session,
    reported_playback,
    team_headers,
    team_release,
)
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.sentence_harness import rehearsed_in_wav, spoken
from tests.tablet_turn_harness import the_room_opens, the_turn_is_scripted
from tests.text_seam_harness import ScriptedAgent


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(
    db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch, store: MemoryStore
):
    guide = ScriptedAgent([])

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belem com Rute")

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=guide)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def the_wheel(client: httpx.AsyncClient, tablet: str) -> dict[str, bool]:
    answered = await client.get(
        f"{PREFIX}/books/Ruth/passages?language=pt", headers=team_headers(tablet)
    )
    assert answered.status_code == 200, answered.text[:300]
    return {entry["pericope"]: entry["approved"] for entry in answered.json()["passages"]}


async def approved(
    client: httpx.AsyncClient, db: AsyncSession, team: Project, tablet: str, pericope: str
) -> None:
    session = await ready_session(db, pericope=pericope, project_id=team.id)
    answered = await client.post(team_release(session.id), headers=team_headers(tablet))
    assert answered.status_code == 200, answered.text[:300]


async def test_a_passage_approved_on_one_tablet_shows_approved_on_another_tablets_wheel(
    client, db_session
) -> None:
    """Acceptance 1."""
    team, _facilitator, [tablet_a, tablet_b] = await claimed_tablets_of_one_team(
        db_session, email="duo@example.com", tablets=2
    )
    await approved(client, db_session, team, tablet_a.credential, "P01")

    wheel = await the_wheel(client, tablet_b.credential)

    assert wheel["P01"] is True
    assert [pericope for pericope, mark in wheel.items() if mark and pericope != "P01"] == []


async def test_a_forced_release_marks_its_passage_approved(client, db_session, room_app) -> None:
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, pericope="P02", project_id=team.id)
    desk, _user = await at_the_desk(db_session, room_app, team)
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text[:300]

    wheel = await the_wheel(client, tablet)

    assert wheel["P02"] is True


async def test_a_passage_the_team_rehearsed_but_never_approved_is_not_approved(
    client, db_session
) -> None:
    """Acceptance 3."""
    team, tablet = await a_claimed_device(db_session)
    await rehearsed_session(db_session, pericope="P01", project_id=team.id)

    wheel = await the_wheel(client, tablet)

    assert wheel["P01"] is False


async def test_a_passage_the_team_talked_in_but_never_recorded_is_not_approved(
    client, db_session
) -> None:
    """Acceptance 4."""
    _team, tablet = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P03"},
    )
    assert opened.status_code == 200, opened.text[:300]
    await the_room_opens(client, tablet, opened.json()["session_id"])

    wheel = await the_wheel(client, tablet)

    assert wheel["P03"] is False
    assert set(wheel.values()) == {False}


async def test_a_zeroed_passage_is_no_longer_approved(client, db_session, room_app) -> None:
    """Acceptance 6."""
    team, tablet = await a_claimed_device(db_session)
    await approved(client, db_session, team, tablet, "P01")
    assert (await the_wheel(client, tablet))["P01"] is True
    desk, _user = await at_the_desk(db_session, room_app, team)
    zeroed = await client.post(
        f"{PREFIX}/facilitator/projects/{team.id}/passages/P01/archive", headers=desk
    )
    assert zeroed.status_code == 200, zeroed.text[:300]

    wheel = await the_wheel(client, tablet)

    assert wheel["P01"] is False


async def test_another_teams_release_never_marks_this_teams_wheel(client, db_session) -> None:
    other, other_tablet = await a_claimed_device(db_session, email="other@example.com")
    _team, tablet = await a_claimed_device(db_session, email="mine@example.com")
    await approved(client, db_session, other, other_tablet, "P01")

    wheel = await the_wheel(client, tablet)

    assert wheel["P01"] is False


async def test_the_panorama_entry_is_never_approved(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    team, tablet = await a_claimed_device(db_session)
    await approved(client, db_session, team, tablet, "P01")

    answered = await client.get(
        f"{PREFIX}/books/Ruth/passages?language=pt", headers=team_headers(tablet)
    )

    first = answered.json()["passages"][0]
    assert (first["kind"], first["approved"]) == ("panorama", False)


async def checked_heard_and_approved(
    client: httpx.AsyncClient, db: AsyncSession, session_id: str, tablet: str
) -> int:
    db.expire_all()
    session = await db.get(IRSession, session_id)
    assert session is not None
    told = await final_segments(db, session.id)
    await reported_playback(
        db,
        session,
        BackTranslationState(
            scope=session.pericope,
            findings=[],
            checked=True,
            analysed_segment_ids=[one.id for one in told],
        ),
    )
    answered = await client.post(team_release(session.id), headers=team_headers(tablet))
    assert answered.status_code == 200, answered.text[:300]
    version: int | None = answered.json()["version"]
    assert version is not None, answered.text[:300]
    return version


async def test_a_re_opened_draft_loses_its_mark_on_every_tablet_until_the_next_approval(
    client, db_session, store
) -> None:
    """ENG-1260, acceptance 7."""
    tablet_a = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    tablet_b = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    session, _parts, frases = await rehearsed_in_wav(db_session, store, [[(0, 1000), (1000, 2000)]])
    assert (
        await checked_heard_and_approved(client, db_session, session.id, tablet_a.credential) == 1
    )
    assert (await the_wheel(client, tablet_b.credential))[P] is True

    reopened = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{frases[0][0].id}/sentence",
        headers=team_headers(tablet_a.credential),
        data={"sentence_id": "sentence-0001", "reopens_the_approved_draft": "true"},
        files={"file": ("frase.wav", spoken(1.0), "audio/wav")},
    )
    assert reopened.status_code == 200, reopened.text[:300]

    assert (await the_wheel(client, tablet_b.credential))[P] is False
    assert (
        await checked_heard_and_approved(client, db_session, session.id, tablet_a.credential) == 2
    )
    assert (await the_wheel(client, tablet_b.credential))[P] is True
