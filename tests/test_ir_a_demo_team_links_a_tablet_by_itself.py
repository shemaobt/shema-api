"""ENG-1629 — a store reviewer, alone with the tablet, reaches a passage through the demo team.

The reviewer types the code the tablet shows into one page the server serves while a demo team
is configured, and the server spends it on that team as a facilitator's Desk spend would. The
demo team never calls a person and never releases to Refine. With no configuration there is
no page and nothing changes.
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import ProjectRole
from app.core.rate_limit import limiter
from app.db.models.device import Device
from app.db.models.internalization_room import IRTakeKind
from app.db.models.project import Project
from app.services.auth.issue_tokens import issue_tokens
from app.services.device.claim_device import claim_device
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from app.services.platform.storage import StoredObject
from app.services.platform.tts import SynthesizedSpeech
from tests.baker import (
    a_language,
    grant_facilitator_app_role,
    make_project,
    make_project_user_access,
    make_user,
)
from tests.device_harness import a_linked_tablet
from tests.hard_stretch_harness import a_new_recording, marks
from tests.hard_stretch_harness import row as session_row
from tests.release_harness import desk_release, ready_session, releases_of, team_release

IR = "/api/internalization-room"
DESK = "/api/facilitator/teams"
PAGE = f"{IR}/demo"
REFUSAL = "That claim code is not valid."
LINKED = "Linked. Go back to the tablet."
DEMO_NAME = "Equipe Demonstração"


class _MemoryStore:
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


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio",
        mime_type="audio/mpeg",
        etag="e",
        cached=False,
        key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
    )
    return entry, False


class Team:
    def __init__(self, team_id: str, name: str, desk: dict[str, str]) -> None:
        self.id = team_id
        self.name = name
        self.desk = desk


async def a_team(db: AsyncSession, *, name: str) -> Team:
    """A team and the headers of the facilitator who facilitates it and nothing else."""
    user = await make_user(db, email=f"fac-{uuid.uuid4().hex[:8]}@example.com")
    language = await a_language(db, name=f"Lingua {name}")
    project = await make_project(db, language.id, name=name)
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    access, _refresh = await issue_tokens(db, user)
    return Team(project.id, name, {"Authorization": f"Bearer {access}"})


@pytest.fixture()
async def demo(db_session: AsyncSession) -> Team:
    return await a_team(db_session, name=DEMO_NAME)


@pytest.fixture()
async def real(db_session: AsyncSession) -> Team:
    return await a_team(db_session, name="Equipe Terena")


@pytest.fixture()
def the_demo_team_is(monkeypatch: pytest.MonkeyPatch):
    def _configure(team_id: str) -> None:
        monkeypatch.setattr(get_settings(), "internalization_room_demo_team_id", team_id)

    return _configure


@pytest.fixture()
async def configured(client, the_demo_team_is, demo: Team) -> Team:
    """The demo team, once the page has served it: serving it is what marks the team."""
    the_demo_team_is(demo.id)
    assert (await client.get(PAGE)).status_code == 200
    return demo


@pytest.fixture()
async def room_app(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room and the Desk on one app, because a demo team is read from both sides."""
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    async def _words(*_: Any, **__: Any) -> str:
        return "a equipe contou o trecho"

    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(bt_api, "heard", _words)
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: _MemoryStore())

    test_app = FastAPI()
    test_app.state.limiter = limiter
    test_app.include_router(room_router, prefix=IR)
    test_app.include_router(facilitator_teams_router, prefix=DESK)
    register_exception_handlers(test_app)
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    limiter.reset()
    yield test_app
    limiter.reset()


def a_caller_at(app: Any, address: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, client=(address, 4321)), base_url="http://test"
    )


@pytest.fixture()
async def client(room_app):
    async with a_caller_at(room_app, "198.51.100.1") as c:
        yield c


# --- what the tablet, the reviewer and the facilitator do ---------------------------------


async def a_code_on_the_tablet(client: httpx.AsyncClient) -> tuple[str, str]:
    shown = await client.post(f"{IR}/devices/code")
    assert shown.status_code == 200, shown.text[:300]
    return shown.json()["device_id"], shown.json()["code"]


async def typed_on_the_page(client: httpx.AsyncClient, code: str) -> httpx.Response:
    return await client.post(PAGE, data={"code": code})


async def the_link(client: httpx.AsyncClient, device_id: str) -> httpx.Response:
    return await client.get(f"{IR}/devices/{device_id}/link")


async def a_tablet_linked_through_the_page(client: httpx.AsyncClient) -> dict[str, str]:
    device_id, code = await a_code_on_the_tablet(client)
    assert (await typed_on_the_page(client, code)).status_code == 200
    collected = await client.post(f"{IR}/devices/{device_id}/credential")
    assert collected.status_code == 200, collected.text[:300]
    return {"X-Device-Credential": collected.json()["credential"], "X-Room-Device": device_id}


async def opens_p01(client: httpx.AsyncClient, tablet: dict[str, str]) -> str:
    opened = await client.post(
        f"{IR}/sessions", headers=tablet, json={"pericope": "P01", "language": "pt"}
    )
    assert opened.status_code == 200, opened.text[:300]
    return opened.json()["session_id"]


async def a_session_with_one_turn(client: httpx.AsyncClient, db: AsyncSession, tablet) -> str:
    from app.services.internalization_room import sessions as room

    session_id = await opens_p01(client, tablet)
    await room.append_exchange(
        db, await session_row(db, session_id), team_utterance="oi", guide_response="ok"
    )
    return session_id


async def a_rehearsal(client: httpx.AsyncClient, session_id: str, tablet) -> str:
    kept = await client.post(
        f"{IR}/sessions/{session_id}/takes",
        headers=tablet,
        data={"kind": IRTakeKind.ENSAIO.value, "scope": "P01"},
        files={"file": ("tomada.m4a", b"a equipe ensaiou a passagem", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text[:300]
    return kept.json()["take_id"]


async def one_stretch_told_until_it_is_hard(
    client: httpx.AsyncClient, session_id: str, tablet, take_id: str
) -> None:
    for _ in range(RETELLS_BEFORE_A_WARNING):
        telling = await client.post(
            f"{IR}/sessions/{session_id}/back-translation/chunks",
            headers=tablet,
            data={"take_id": take_id, "starts_ms": "0", "ends_ms": "9000", "retelling": "true"},
            files={"file": ("trecho.m4a", a_new_recording(), "audio/mp4")},
        )
        assert telling.status_code == 200, telling.text[:300]


async def the_queue(client: httpx.AsyncClient, team: Team) -> dict:
    listed = await client.get(f"{IR}/facilitator/sessions", headers=team.desk)
    assert listed.status_code == 200, listed.text[:300]
    return listed.json()


async def queued_session_ids(client: httpx.AsyncClient, team: Team) -> set[str]:
    return {row["session_id"] for row in (await the_queue(client, team))["sessions"]}


async def queued_device_ids(client: httpx.AsyncClient, team: Team) -> set[str]:
    return {row["device_id"] for row in (await the_queue(client, team))["devices"]}


async def device_row(db: AsyncSession, device_id: str) -> Device:
    result = await db.execute(
        select(Device).where(Device.id == device_id).execution_options(populate_existing=True)
    )
    return result.scalar_one()


# --- The page -----------------------------------------------------------------------------


async def test_the_page_spends_a_shown_code_on_the_demo_team_and_the_tablets_next_poll_finds_it_linked(  # noqa: E501
    client, configured: Team, db_session: AsyncSession
) -> None:
    form = await client.get(PAGE)
    assert form.status_code == 200, form.text[:300]
    assert form.headers["content-type"].startswith("text/html")
    assert 'name="code"' in form.text

    device_id, code = await a_code_on_the_tablet(client)
    spent = await typed_on_the_page(client, code)

    assert spent.status_code == 200, spent.text[:300]
    assert LINKED in spent.text
    link = await the_link(client, device_id)
    assert link.status_code == 200, link.text[:300]
    assert link.json()["project_id"] == configured.id

    collected = await client.post(f"{IR}/devices/{device_id}/credential")
    assert collected.status_code == 200, collected.text[:300]
    tablet = {"X-Device-Credential": collected.json()["credential"], "X-Room-Device": device_id}
    session_id = await opens_p01(client, tablet)
    assert (await session_row(db_session, session_id)).project_id == configured.id


async def test_a_code_the_desk_spent_and_an_unknown_code_are_refused_with_the_same_answer(
    client, configured: Team, real: Team, db_session: AsyncSession
) -> None:
    device_id, code = await a_code_on_the_tablet(client)
    await claim_device(db_session, code=code, project_id=real.id)

    spent = await typed_on_the_page(client, code)
    unknown = await typed_on_the_page(client, "AAA-AAAA")

    assert spent.status_code == 400
    assert unknown.status_code == 400
    assert REFUSAL in spent.text
    assert spent.text == unknown.text
    assert (await the_link(client, device_id)).json()["project_id"] == real.id


async def test_a_code_the_page_already_spent_is_refused_and_stays_on_the_demo_team(
    client, configured: Team
) -> None:
    device_id, code = await a_code_on_the_tablet(client)
    assert (await typed_on_the_page(client, code)).status_code == 200

    again = await typed_on_the_page(client, code)

    assert again.status_code == 400
    assert REFUSAL in again.text
    assert (await the_link(client, device_id)).json()["project_id"] == configured.id


async def test_a_code_typed_with_a_space_or_a_mobile_dash_in_lower_case_is_spent(
    client, configured: Team
) -> None:
    spaced_device, spaced = await a_code_on_the_tablet(client)
    dashed_device, dashed = await a_code_on_the_tablet(client)

    by_space = await typed_on_the_page(client, f"  {spaced.lower().replace('-', ' ')} ")
    by_dash = await typed_on_the_page(client, dashed.replace("-", "\u2013"))

    assert by_space.status_code == 200, by_space.text[:300]
    assert by_dash.status_code == 200, by_dash.text[:300]
    assert (await the_link(client, spaced_device)).json()["project_id"] == configured.id
    assert (await the_link(client, dashed_device)).json()["project_id"] == configured.id


async def test_with_no_demo_team_the_page_answers_404_and_nothing_is_spent(
    client, the_demo_team_is
) -> None:
    the_demo_team_is("")
    device_id, code = await a_code_on_the_tablet(client)

    assert (await client.get(PAGE)).status_code == 404
    assert (await typed_on_the_page(client, code)).status_code == 404
    assert (await the_link(client, device_id)).status_code == 204


async def test_with_no_demo_team_the_page_answers_404_however_often_it_is_asked(
    client, the_demo_team_is
) -> None:
    the_demo_team_is("")

    answers = {(await typed_on_the_page(client, "AAA-AAAA")).status_code for _ in range(11)}

    assert answers == {404}


async def test_a_missing_or_overlong_code_is_refused_with_the_one_answer(
    client, configured: Team
) -> None:
    unknown = await typed_on_the_page(client, "AAA-AAAA")
    missing = await client.post(PAGE, data={})
    overlong = await typed_on_the_page(client, "A" * 33)

    assert {missing.status_code, overlong.status_code} == {400}
    assert missing.text == unknown.text
    assert overlong.text == unknown.text


async def test_a_configured_id_that_names_no_team_is_no_demo_team(client, the_demo_team_is) -> None:
    the_demo_team_is(str(uuid.uuid4()))
    device_id, code = await a_code_on_the_tablet(client)

    assert (await client.get(PAGE)).status_code == 404
    assert (await typed_on_the_page(client, code)).status_code == 404
    assert (await the_link(client, device_id)).status_code == 204


async def test_the_page_takes_ten_codes_a_minute_whoever_sends_them(
    client, room_app, configured: Team
) -> None:
    for _ in range(10):
        assert (await typed_on_the_page(client, "AAA-AAAA")).status_code == 400

    device_id, code = await a_code_on_the_tablet(client)
    async with a_caller_at(room_app, "203.0.113.9") as another:
        eleventh = await typed_on_the_page(another, code)

    assert eleventh.status_code == 429
    assert (await the_link(client, device_id)).status_code == 204


# --- Halts --------------------------------------------------------------------------------


async def test_a_demo_teams_halt_is_stamped_by_the_server_and_never_reaches_the_queue(
    client, configured: Team, db_session: AsyncSession
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    session_id = await a_session_with_one_turn(client, db_session, tablet)

    asked = await client.post(f"{IR}/sessions/{session_id}/needs-person", headers=tablet)

    assert asked.status_code == 200, asked.text[:300]
    state = (await client.get(f"{IR}/sessions/{session_id}", headers=tablet)).json()
    assert state["status"] == "needs_person", "a visita do servidor levantou a parada do tablet"
    assert state["halt"] == "blocking"
    assert session_id not in await queued_session_ids(client, configured)
    written = await session_row(db_session, session_id)
    assert written.attended_at is not None
    assert written.attended_by is None
    assert written.halts_raised == 1

    assert await opens_p01(client, tablet) == session_id
    state = (await client.get(f"{IR}/sessions/{session_id}", headers=tablet)).json()
    assert state["status"] == "in_progress"


async def test_a_demo_teams_hard_stretch_keeps_its_warning_attended_and_calls_nobody(
    client, configured: Team, db_session: AsyncSession
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    session_id = await a_session_with_one_turn(client, db_session, tablet)
    take_id = await a_rehearsal(client, session_id, tablet)

    await one_stretch_told_until_it_is_hard(client, session_id, tablet, take_id)

    assert len(await marks(db_session, session_id)) == 1
    state = (await client.get(f"{IR}/sessions/{session_id}", headers=tablet)).json()
    assert state["halt"] is None
    assert session_id not in await queued_session_ids(client, configured)
    written = await session_row(db_session, session_id)
    assert written.attended_at is not None
    assert written.attended_by is None


async def test_a_warning_on_a_demo_room_already_halted_stamps_it_and_leaves_the_halt_standing(
    client, configured: Team, db_session: AsyncSession
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    session_id = await a_session_with_one_turn(client, db_session, tablet)
    take_id = await a_rehearsal(client, session_id, tablet)
    await client.post(f"{IR}/sessions/{session_id}/needs-person", headers=tablet)
    undone = await client.delete(
        f"{IR}/facilitator/sessions/{session_id}/attended", headers=configured.desk
    )
    assert undone.json()["status"] == "needs_person", undone.text[:300]
    assert session_id in await queued_session_ids(client, configured)

    await one_stretch_told_until_it_is_hard(client, session_id, tablet, take_id)

    state = (await client.get(f"{IR}/sessions/{session_id}", headers=tablet)).json()
    assert state["status"] == "needs_person"
    assert state["halt"] == "blocking"
    assert session_id not in await queued_session_ids(client, configured)


async def test_a_demo_tablet_that_asks_for_a_person_without_a_session_is_attended_at_once(
    client, configured: Team, db_session: AsyncSession
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    device_id = tablet["X-Room-Device"]

    asked = await client.post(f"{IR}/devices/{device_id}/needs-person", headers=tablet)

    assert asked.status_code == 200, asked.text[:300]
    assert asked.json()["needs_person_since"]
    assert device_id not in await queued_device_ids(client, configured)
    written = await device_row(db_session, device_id)
    assert written.attended_at is not None
    assert written.attended_by is None
    assert written.needs_person_since is None


async def test_a_real_teams_halt_still_calls_a_person_while_a_demo_team_is_configured(
    client, configured: Team, real: Team, db_session: AsyncSession
) -> None:
    linked = await a_linked_tablet(db_session, team_id=real.id)
    tablet = linked.headers
    session_id = await a_session_with_one_turn(client, db_session, tablet)

    asked = await client.post(f"{IR}/sessions/{session_id}/needs-person", headers=tablet)
    halted = await client.post(f"{IR}/devices/{linked.device_id}/needs-person", headers=tablet)

    assert asked.json()["needs_person"] is True
    assert halted.status_code == 200, halted.text[:300]
    assert session_id in await queued_session_ids(client, real)
    assert linked.device_id in await queued_device_ids(client, real)


async def test_after_the_window_closes_the_demo_teams_halts_are_still_attended(
    client, configured: Team, the_demo_team_is, db_session: AsyncSession
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    session_id = await a_session_with_one_turn(client, db_session, tablet)
    the_demo_team_is("")

    asked = await client.post(f"{IR}/sessions/{session_id}/needs-person", headers=tablet)
    halted = await client.post(
        f"{IR}/devices/{tablet['X-Room-Device']}/needs-person", headers=tablet
    )

    assert asked.status_code == 200, asked.text[:300]
    assert halted.status_code == 200, halted.text[:300]
    assert session_id not in await queued_session_ids(client, configured)
    assert tablet["X-Room-Device"] not in await queued_device_ids(client, configured)


async def test_a_real_team_is_never_marked_as_the_demo_team(
    client, configured: Team, real: Team, db_session: AsyncSession
) -> None:
    await a_tablet_linked_through_the_page(client)
    await a_linked_tablet(db_session, team_id=real.id)

    async def marked(team: Team) -> bool:
        row = await db_session.execute(
            select(Project.is_demo_team)
            .where(Project.id == team.id)
            .execution_options(populate_existing=True)
        )
        return row.scalar_one()

    assert await marked(configured) is True
    assert await marked(real) is False


# --- The Desk -----------------------------------------------------------------------------


async def test_the_desk_lists_the_demo_team_under_its_own_name_with_its_session(
    client, configured: Team, db_session: AsyncSession
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    session_id = await a_session_with_one_turn(client, db_session, tablet)

    teams = await client.get(DESK, headers=configured.desk)
    sessions = await client.get(f"{DESK}/{configured.id}/sessions", headers=configured.desk)

    assert teams.status_code == 200, teams.text[:300]
    assert {team["name"] for team in teams.json()["teams"] if team["team_id"] == configured.id} == {
        DEMO_NAME
    }
    assert session_id in {card["session_id"] for card in sessions.json()}


async def test_a_facilitator_zerars_the_demo_teams_passage_like_any_teams(
    client, configured: Team
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    first = await opens_p01(client, tablet)

    zerado = await client.post(
        f"{IR}/facilitator/projects/{configured.id}/passages/P01/archive",
        headers=configured.desk,
    )

    assert zerado.status_code == 200, zerado.text[:300]
    assert zerado.json()["archived"] is True
    assert await opens_p01(client, tablet) != first


# --- Release ------------------------------------------------------------------------------


async def test_the_demo_teams_approval_is_refused_and_nothing_reaches_refine(
    client, configured: Team, db_session: AsyncSession
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    session = await ready_session(db_session, project_id=configured.id)

    approved = await client.post(team_release(session.id), headers=tablet)

    assert approved.status_code == 200, approved.text[:300]
    assert approved.json()["blockers"] == ["demo_team_never_releases"]
    assert approved.json()["version"] is None
    assert await releases_of(db_session, session.id) == []


async def test_a_facilitator_cannot_force_the_demo_teams_release(
    client, configured: Team, db_session: AsyncSession
) -> None:
    session = await ready_session(db_session, project_id=configured.id)

    forced = await client.post(
        desk_release(session.id), headers=configured.desk, json={"force": True}
    )

    assert forced.status_code == 409, forced.text[:300]
    assert await releases_of(db_session, session.id) == []


async def test_the_desks_refine_artifact_refuses_the_demo_team(
    client, configured: Team, db_session: AsyncSession
) -> None:
    session = await ready_session(db_session, project_id=configured.id)

    read = await client.get(desk_release(session.id), headers=configured.desk)

    assert read.status_code == 409, read.text[:300]


async def test_after_the_window_closes_the_demo_teams_release_is_still_refused(
    client, configured: Team, the_demo_team_is, db_session: AsyncSession
) -> None:
    tablet = await a_tablet_linked_through_the_page(client)
    session = await ready_session(db_session, project_id=configured.id)
    the_demo_team_is("")

    approved = await client.post(team_release(session.id), headers=tablet)
    forced = await client.post(
        desk_release(session.id), headers=configured.desk, json={"force": True}
    )

    assert approved.json()["blockers"] == ["demo_team_never_releases"]
    assert forced.status_code == 409, forced.text[:300]
    assert await releases_of(db_session, session.id) == []


async def test_a_real_teams_release_is_minted_as_before_while_a_demo_team_is_configured(
    client, configured: Team, real: Team, db_session: AsyncSession
) -> None:
    linked = await a_linked_tablet(db_session, team_id=real.id)
    session = await ready_session(db_session, project_id=real.id)

    approved = await client.post(team_release(session.id), headers=linked.headers)

    assert approved.status_code == 200, approved.text[:300]
    assert approved.json()["version"] == 1
