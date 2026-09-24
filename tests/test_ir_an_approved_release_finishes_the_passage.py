from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.sessions import back_translation_of, report_playback
from tests.baker import having_finished_the_passage, make_app, make_role, open_ir_session
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    KEY,
    P02,
    PREFIX,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    at_the_desk,
    desk_release,
    releases_of,
    team_headers,
    team_release,
    the_one_part_of,
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.facilitator.teams import facilitator_teams_router
    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    test_app.include_router(facilitator_teams_router, prefix="/api/facilitator/teams")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _below_the_floor(db: AsyncSession, session: IRSession) -> IRSession:
    session.coverage_state = initial_state(P02)
    await db.commit()
    return session


async def _told_back_clean_and_heard_through(db: AsyncSession, session: IRSession) -> IRSession:
    state = back_translation_of(session)
    state.checked = True
    state.findings = []
    part = await the_one_part_of(db, session)
    await report_playback(
        db,
        session,
        state,
        played_by_take=[
            PlayedTake(take_id=part.id, played_ranges=[(0, CLIP_MS)], clip_duration_ms=CLIP_MS)
        ],
        played_ranges=[[0, CLIP_MS]],
        clip_duration_ms=CLIP_MS,
    )
    return session


async def test_a_passage_below_the_floor_told_back_clean_and_heard_through_is_approved(
    client, db_session
):
    project, credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    await _told_back_clean_and_heard_through(db_session, session)
    await _below_the_floor(db_session, session)

    approved = await client.post(team_release(session.id), headers=team_headers(credential))

    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["blockers"] == [], (
        "a aprovação recusava pelo piso de cobertura, um portão que a dela nunca teve"
    )
    assert body["version"] == 1
    assert [row.version for row in await releases_of(db_session, session.id)] == [1]


async def test_an_open_finding_below_the_floor_is_refused_by_her_gate_alone_and_forced(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session)
    session = await _below_the_floor(
        db_session, await a_p02_telling_with_the_swapped_cause(db_session, project)
    )
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    refused = await client.post(team_release(session.id), headers=team_headers(credential))
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert refused.status_code == 200, refused.text
    assert refused.json()["blockers"] == ["telling_back_not_checked"], (
        "o piso ia junto na recusa, e o tablet não tinha porta para ele"
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["version"] == 1, (
        "a força do facilitador esbarrava no piso, que não é forçável"
    )


async def test_an_approved_release_closes_the_passage_on_the_desk_and_the_next_one_is_current(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session)
    await having_finished_the_passage(
        db_session, await open_ir_session(db_session, pericope="P01", project_id=project.id)
    )
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    await _told_back_clean_and_heard_through(db_session, session)
    await _below_the_floor(db_session, session)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    book = await client.get(f"/api/facilitator/teams/{project.id}/pericopes", headers=desk)

    assert approved.json()["version"] == 1
    assert book.status_code == 200, book.text
    where = {entry["pericope"]: entry["position"] for entry in book.json()}
    assert (where["P01"], where["P02"], where["P03"]) == ("closed", "closed", "current"), (
        "o tablet fechava o colar na aprovação e o servidor mantinha a passagem aberta, "
        "porque só contava o ended_at do piso"
    )


async def test_the_desk_card_reads_an_approved_session_complete_at_its_first_approval(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    await _told_back_clean_and_heard_through(db_session, session)
    await _below_the_floor(db_session, session)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    await client.post(team_release(session.id), headers=team_headers(credential))
    (first,) = await releases_of(db_session, session.id)
    first.approved_at = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)
    db_session.add(
        IRRelease(
            session_id=session.id,
            project_id=project.id,
            pericope=P02,
            version=2,
            package_sha256="f" * 64,
            packet={},
            approved_at=datetime(2026, 9, 24, 11, 30, tzinfo=UTC),
        )
    )
    await db_session.commit()

    history = await client.get(f"/api/facilitator/teams/{project.id}/sessions", headers=desk)

    assert history.status_code == 200, history.text
    (card,) = history.json()
    assert card["state"] == "complete", (
        "a sessão aprovada abaixo do piso ficava em andamento e, seis horas depois, abandonada"
    )
    assert card["ended_at"].startswith("2026-09-24T10:00:00"), (
        "o fim andava com a re-aprovação em vez de ficar no instante em que a equipe aprovou"
    )
