"""ENG-1597 — each passage the Desk lists carries its latest release and whether it is approved.

Marcia's rows read the release, «versão 2 · forçada às 14h10», and her count is of approved
passages: a finished session without a release approves nothing. The cases build releases,
findings and archives through the room's own routes and read what the facilitator's two
routes answer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
)
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.sessions import create_session
from tests.baker import having_finished_the_passage, make_app, make_role, open_ir_session
from tests.opening_harness import desk_routes
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
from tests.room_harness import room_client, the_bucket_is_in_memory, upload_a_part

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]
FIRST = CANON[0]
PANORAMA = f"OV-{ROOM_BOOK}"


@pytest.fixture()
async def room(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
async def desk_client(db_session: AsyncSession):
    async with desk_routes(db_session) as c:
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
    room, desk_client, db_session, room_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session = await ready_session(db_session, project_id=team.id)
    await approved_by_the_team(room, tablet, session)
    the_bucket_is_in_memory(monkeypatch)
    again = await upload_a_part(
        room, session.id, part=None, audio=b"recorded again", headers=team_headers(tablet)
    )
    assert again.status_code == 200, again.text[:300]
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


async def test_the_standing_names_the_session_holding_takes_over_a_newer_one_without(
    desk_client, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    rehearsed, _ = await rehearsed_session(db_session, project_id=team.id, language="pt")
    bare = await open_ir_session(db_session, pericope=P, project_id=team.id)
    await db_session.execute(
        update(IRSession).where(IRSession.id == bare.id).values(messages=[{"role": "user"}])
    )
    await last_active_at(db_session, rehearsed, datetime(2026, 10, 1, 9, tzinfo=UTC))
    await last_active_at(db_session, bare, datetime(2026, 10, 1, 10, tzinfo=UTC))

    passage = (await listed(desk_client, desk, team.id))[P]

    assert passage["session_id"] == rehearsed.id
    assert passage["has_takes"] is True


async def test_a_session_without_a_take_is_named_and_holds_none(
    desk_client, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    bare = await open_ir_session(db_session, pericope=P, project_id=team.id)

    passage = (await listed(desk_client, desk, team.id))[P]

    assert passage["session_id"] == bare.id
    assert passage["has_takes"] is False


async def test_a_passage_never_opened_names_no_session(desk_client, db_session, room_app) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)

    passage = (await listed(desk_client, desk, team.id))[CANON[-1]]

    assert passage["session_id"] is None
    assert passage["has_takes"] is False


async def test_an_archived_session_is_never_named(room, desk_client, db_session, room_app) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    await rehearsed_session(db_session, project_id=team.id)
    zerado = await room.post(
        f"{PREFIX}/facilitator/projects/{team.id}/passages/{P}/archive", headers=desk
    )
    assert zerado.status_code == 200, zerado.text[:300]

    passage = (await listed(desk_client, desk, team.id))[P]

    assert passage["session_id"] is None
    assert passage["has_takes"] is False


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
        await having_finished_the_passage(
            db_session, await open_ir_session(db_session, pericope=pericope, project_id=team.id)
        )
        session = await ready_session(db_session, pericope=pericope, project_id=team.id)
        await approved_by_the_team(room, tablet, session)
    await having_finished_the_passage(
        db_session, await open_ir_session(db_session, pericope=FIRST, project_id=team.id)
    )

    detail = await desk_client.get(f"/api/facilitator/teams/{team.id}", headers=desk)

    assert detail.status_code == 200, detail.text[:300]
    assert detail.json()["approved_total"] == 2
    assert detail.json()["closed_total"] == 3


async def test_a_passage_whose_draft_was_re_opened_reads_not_approved_and_keeps_its_release(
    room, desk_client, db_session, room_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ENG-1260: the team recorded the passage again over its approved v1."""
    the_bucket_is_in_memory(monkeypatch)
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    sessions = {}
    for pericope in ("P02", "P03"):
        sessions[pericope] = await ready_session(db_session, pericope=pericope, project_id=team.id)
        await approved_by_the_team(room, tablet, sessions[pericope])
    before = (await listed(desk_client, desk, team.id))["P03"]
    assert (before["approved"], before["release"]["version"]) == (True, 1)
    assert (await desk_client.get(f"/api/facilitator/teams/{team.id}", headers=desk)).json()[
        "approved_total"
    ] == 2

    again = await upload_a_part(
        room,
        sessions["P03"].id,
        part=None,
        audio=b"a passagem gravada de novo",
        headers=team_headers(tablet),
    )
    assert again.status_code == 200, again.text[:300]

    after = (await listed(desk_client, desk, team.id))["P03"]
    assert (after["approved"], after["release"]["version"]) == (False, 1)
    detail = await desk_client.get(f"/api/facilitator/teams/{team.id}", headers=desk)
    assert detail.json()["approved_total"] == 1


async def statements_of(test_engine, read) -> int:
    from sqlalchemy import event

    seen: list[str] = []

    def noted(conn, cursor, statement, parameters, context, executemany) -> None:
        seen.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", noted)
    try:
        await read()
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", noted)
    return len(seen)


async def test_whether_each_passage_is_approved_costs_the_same_for_one_release_and_for_ten(
    room, desk_client, db_session, room_app, test_engine
) -> None:
    """Approval is a comparison of takes, read for the whole team at once (ADR 0081)."""
    counted = []
    for released in (CANON[:1], CANON[:10]):
        team, tablet = await a_claimed_device(db_session)
        desk, _ = await at_the_desk(db_session, room_app, team)
        for pericope in released:
            session = await ready_session(db_session, pericope=pericope, project_id=team.id)
            await approved_by_the_team(room, tablet, session)
        passages = await listed(desk_client, desk, team.id)
        assert sum(entry["approved"] for entry in passages.values()) == len(released)

        async def the_two_desk_reads(team_id: str = team.id, headers: dict = desk) -> None:
            await desk_client.get(f"/api/facilitator/teams/{team_id}", headers=headers)
            await desk_client.get(f"/api/facilitator/teams/{team_id}/pericopes", headers=headers)

        counted.append(await statements_of(test_engine, the_two_desk_reads))

    assert counted[0] == counted[1], f"uma liberação custou {counted[0]}, dez custaram {counted[1]}"


async def stored_release_id(db: AsyncSession, team_id: str, version: int) -> str:
    rows = await db.execute(
        select(IRRelease).where(IRRelease.project_id == team_id, IRRelease.version == version)
    )
    return rows.scalars().one().packet["release_id"]


async def test_a_passage_approved_as_version_1_by_the_team_reads_its_release_id_version_1_not_forced(  # noqa: E501
    room, desk_client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session, language_name="Guarani")
    desk, _ = await at_the_desk(db_session, room_app, team)
    await approved_by_the_team(room, tablet, await ready_session(db_session, project_id=team.id))

    release = (await listed(desk_client, desk, team.id))[P]["release"]

    assert release["release_id"] == f"internalize-guarani-{P.lower()}-v1"
    assert release["release_id"] == await stored_release_id(db_session, team.id, 1)
    assert release["version"] == 1
    assert release["forced_at"] is None


async def test_a_forced_passage_reads_its_release_id_with_forced_at_set(
    room, desk_client, db_session, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session, language_name="Guarani")
    desk, _ = await at_the_desk(db_session, room_app, team)
    session = await ready_session(
        db_session, project_id=team.id, tell=told_back_with_an_open_finding
    )
    forced = await room.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text[:300]

    release = (await listed(desk_client, desk, team.id))[P]["release"]

    assert release["release_id"] == f"internalize-guarani-{P.lower()}-v1"
    assert release["release_id"] == await stored_release_id(db_session, team.id, 1)
    assert release["version"] == 1
    assert release["forced_at"] is not None


async def test_a_passage_never_approved_reads_no_release(desk_client, db_session, room_app) -> None:
    team, _tablet = await a_claimed_device(db_session, language_name="Guarani")
    desk, _ = await at_the_desk(db_session, room_app, team)

    assert (await listed(desk_client, desk, team.id))[P]["release"] is None


async def test_a_passage_reset_with_zerar_and_approved_again_reads_version_2_with_the_version_2_id(
    room, desk_client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session, language_name="Guarani")
    desk, _ = await at_the_desk(db_session, room_app, team)
    await approved_by_the_team(room, tablet, await ready_session(db_session, project_id=team.id))
    zerado = await room.post(
        f"{PREFIX}/facilitator/projects/{team.id}/passages/{P}/archive", headers=desk
    )
    assert zerado.status_code == 200, zerado.text[:300]
    await approved_by_the_team(room, tablet, await ready_session(db_session, project_id=team.id))

    release = (await listed(desk_client, desk, team.id))[P]["release"]

    assert release["version"] == 2
    assert release["release_id"] == f"internalize-guarani-{P.lower()}-v2"
    assert release["release_id"] == await stored_release_id(db_session, team.id, 2)
