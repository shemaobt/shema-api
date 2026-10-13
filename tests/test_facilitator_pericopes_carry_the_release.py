"""ENG-1597 — each passage the Desk lists carries its latest release and a reference in one form.

Marcia's rows read the release, «versão 2 · forçada às 14h10», and her count is of approved
passages: a finished session without a release approves nothing. The cases build releases,
findings and archives through the room's own routes and read what the facilitator's two
routes answer.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
)
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.sessions import create_session
from tests.baker import having_finished_the_passage, make_app, make_role, open_ir_session
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    checked_telling_back,
    desk_release,
    one_stretch,
    ready_session,
    rehearsed_session,
    reported_playback,
    team_headers,
    team_release,
    told_back_with_an_open_finding,
)

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]
FIRST = CANON[0]
PANORAMA = f"OV-{ROOM_BOOK}"
EN_DASH = "\u2013"


@pytest.fixture()
async def room(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    tablet = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test", headers=tablet.headers
    ) as c:
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
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def told_back_with_two_open_findings(
    db: AsyncSession, session: IRSession
) -> BackTranslationState:
    told = await one_stretch(db, session)
    return BackTranslationState(
        scope=session.pericope,
        findings=[
            Finding(
                kind=FindingKind.ADDITION, note="Noemi voltou alegre", segment_id=told.id, chunk=1
            ),
            Finding(
                kind=FindingKind.ADDITION, note="Rute ficou em Moabe", segment_id=told.id, chunk=2
            ),
        ],
        checked=False,
        analysed_segment_ids=[told.id],
    )


async def approved_by_the_team(room: httpx.AsyncClient, tablet: str, session: IRSession) -> None:
    approved = await room.post(team_release(session.id), headers=team_headers(tablet))
    assert approved.status_code == 200, approved.text[:300]


async def last_active_at(db: AsyncSession, session: IRSession, moment: datetime) -> None:
    await db.execute(update(IRSession).where(IRSession.id == session.id).values(updated_at=moment))
    await db.commit()


async def listing(desk_client: httpx.AsyncClient, desk: dict[str, str], team_id: str) -> list:
    answered = await desk_client.get(f"/api/facilitator/teams/{team_id}/pericopes", headers=desk)
    assert answered.status_code == 200, answered.text[:300]
    return answered.json()


async def listed(desk_client: httpx.AsyncClient, desk: dict[str, str], team_id: str) -> dict:
    return {entry["pericope"]: entry for entry in await listing(desk_client, desk, team_id)}


async def test_a_passage_forced_at_version_2_with_two_open_findings_on_its_latest_session_reads_version_2_forced_two_open_findings_and_approved(  # noqa: E501
    room, desk_client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session = await ready_session(db_session, project_id=team.id)
    await approved_by_the_team(room, tablet, session)
    await reported_playback(
        db_session, session, await told_back_with_two_open_findings(db_session, session)
    )
    forced = await room.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text[:300]

    passage = (await listed(desk_client, desk, team.id))[P]

    assert passage["release"]["version"] == 2
    assert passage["release"]["forced_at"] is not None
    assert passage["open_findings"] == 2
    assert passage["approved"] is True


async def test_a_passage_approved_once_without_force_reads_version_1_not_forced_no_open_findings(
    room, desk_client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await approved_by_the_team(room, tablet, await ready_session(db_session, project_id=team.id))

    passage = (await listed(desk_client, desk, team.id))[P]

    assert passage["release"]["version"] == 1
    assert passage["release"]["forced_at"] is None
    assert passage["release"]["approved_at"] is not None
    assert passage["open_findings"] == 0
    assert passage["approved"] is True


async def test_a_finished_session_without_a_release_does_not_approve_its_passage(
    desk_client, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await having_finished_the_passage(
        db_session, await open_ir_session(db_session, pericope=FIRST, project_id=team.id)
    )

    passage = (await listed(desk_client, desk, team.id))[FIRST]

    assert passage["position"] == "closed"
    assert passage["release"] is None
    assert passage["approved"] is False


async def test_a_passage_in_progress_counts_the_open_findings_on_its_latest_session(
    desk_client, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session, _take = await rehearsed_session(db_session, project_id=team.id)
    await reported_playback(
        db_session, session, await told_back_with_an_open_finding(db_session, session)
    )

    passage = (await listed(desk_client, desk, team.id))[P]

    assert passage["open_findings"] == 1
    assert passage["release"] is None


async def test_the_latest_session_is_the_most_recently_active_one_across_languages(
    desk_client, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    portuguese, _ = await rehearsed_session(db_session, project_id=team.id, language="pt")
    await reported_playback(
        db_session, portuguese, await told_back_with_an_open_finding(db_session, portuguese)
    )
    english, _ = await rehearsed_session(db_session, project_id=team.id, language="en")
    await reported_playback(db_session, english, await checked_telling_back(db_session, english))
    earlier = datetime(2026, 10, 1, 9, tzinfo=UTC)
    later = earlier + timedelta(hours=1)

    await last_active_at(db_session, portuguese, earlier)
    await last_active_at(db_session, english, later)
    english_latest = (await listed(desk_client, desk, team.id))[P]["open_findings"]
    await last_active_at(db_session, portuguese, later + timedelta(hours=1))
    portuguese_latest = (await listed(desk_client, desk, team.id))[P]["open_findings"]

    assert (english_latest, portuguese_latest) == (0, 1)


async def test_an_archived_release_does_not_approve_the_passage(
    room, desk_client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await approved_by_the_team(room, tablet, await ready_session(db_session, project_id=team.id))
    zerado = await room.post(
        f"{PREFIX}/facilitator/projects/{team.id}/passages/{P}/archive", headers=desk
    )
    assert zerado.status_code == 200, zerado.text[:300]

    archived = (await listed(desk_client, desk, team.id))[P]
    await approved_by_the_team(room, tablet, await ready_session(db_session, project_id=team.id))
    approved_again = (await listed(desk_client, desk, team.id))[P]

    assert archived["release"] is None
    assert archived["approved"] is False
    assert approved_again["release"]["version"] == 2


async def test_p14s_reference_is_written_with_an_en_dash_in_portuguese(
    desk_client, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)

    assert (await listed(desk_client, desk, team.id))["P14"]["reference"] == f"Rute 4:18{EN_DASH}22"


async def test_p02s_reference_is_written_in_portuguese(desk_client, db_session, room_app) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)

    assert (await listed(desk_client, desk, team.id))["P02"]["reference"] == f"Rute 1:6{EN_DASH}14"


async def test_every_passages_reference_has_one_form(desk_client, db_session, room_app) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)

    references = [entry["reference"] for entry in await listing(desk_client, desk, team.id)]

    assert len(references) == 14
    assert all(re.fullmatch(rf"Rute \d+:\d+{EN_DASH}\d+", reference) for reference in references)


async def test_the_listing_holds_the_fourteen_passages_and_no_panorama(
    desk_client, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await create_session(db_session, pericope=PANORAMA, project_id=team.id)

    passages = await listed(desk_client, desk, team.id)

    assert len(passages) == 14
    assert PANORAMA not in passages


async def test_the_team_detail_counts_approved_passages(
    room, desk_client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    for pericope in ("P02", "P03"):
        session = await ready_session(db_session, pericope=pericope, project_id=team.id)
        await approved_by_the_team(room, tablet, session)
        await having_finished_the_passage(db_session, session)
    await having_finished_the_passage(
        db_session, await open_ir_session(db_session, pericope=FIRST, project_id=team.id)
    )

    detail = await desk_client.get(f"/api/facilitator/teams/{team.id}", headers=desk)

    assert detail.status_code == 200, detail.text[:300]
    assert detail.json()["approved_total"] == 2
    assert detail.json()["closed_total"] == 3
