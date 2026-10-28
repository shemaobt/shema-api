"""ENG-1305 — «Aprovar mesmo assim (forçar)»: the facilitator forces a passage past its gate.

Every **Blocker** yields to the force but a passage with no rehearsal take, and the
**Forced release** records the blockers it passed (ADR 0075). The force is addressed to the
passage, like the Zerar: the room picks the passage's live session that holds rehearsal takes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.services.auth.issue_tokens import issue_tokens
from app.services.internalization_room.archives import archive_pericope
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
)
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.segments import capture_segment
from app.services.internalization_room.sessions import create_session
from tests.baker import grant_room_app_role, make_app, make_role, make_user
from tests.opening_harness import desk_routes
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    P02,
    P,
    a_claimed_device,
    a_rehearsal_only_half_heard,
    at_the_desk,
    checked_telling_back,
    desk_passage_release,
    desk_release,
    ensaio_take,
    ready_session,
    rehearsed_session,
    releases_of,
    reported_playback,
    team_headers,
    team_release,
    the_part_recorded_again,
)
from tests.room_harness import room_client

FORCE = {"force": True}


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


async def a_disputed_passage(db: AsyncSession, project_id: str) -> IRSession:
    """Two rehearsal takes, the telling-back not checked and one stretch nobody told back.

    The first part is told back and carries a finding the team did not resolve; the second is
    cut into a stretch with no words on it. Both parts were played through.
    """
    session, first = await rehearsed_session(db, project_id=project_id, ordinal=1)
    second = ensaio_take(session.id, ordinal=2, sha256="b" * 64, project_id=project_id)
    db.add(second)
    await db.commit()
    told = await capture_segment(
        db,
        session,
        take_id=first.id,
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id="retro-1",
        transcript="Noemi voltou com Rute",
    )
    await capture_segment(db, session, take_id=second.id, starts_ms=0, ends_ms=CLIP_MS)
    await reported_playback(
        db,
        session,
        BackTranslationState(
            scope=session.pericope,
            findings=[
                Finding(
                    kind=FindingKind.ADDITION,
                    note="a equipe disse que Noemi voltou alegre",
                    segment_id=told.id,
                    chunk=1,
                )
            ],
            checked=False,
            analysed_segment_ids=[told.id],
        ),
    )
    return session


async def a_passage_with_no_rehearsal_take(db: AsyncSession, project_id: str) -> IRSession:
    session = await create_session(db, pericope=P, project_id=project_id)
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await db.commit()
    return session


async def releases_of_team(db: AsyncSession, project_id: str) -> list[IRRelease]:
    rows = await db.execute(
        select(IRRelease).where(IRRelease.project_id == project_id).order_by(IRRelease.version)
    )
    return list(rows.scalars().all())


async def last_active_at(db: AsyncSession, session: IRSession, moment: datetime) -> None:
    await db.execute(update(IRSession).where(IRSession.id == session.id).values(updated_at=moment))
    await db.commit()


async def test_a_passage_with_two_takes_an_unchecked_telling_back_and_an_untold_stretch_is_forced_with_both_blockers_recorded(  # noqa: E501
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    session = await a_disputed_passage(db_session, team.id)
    desk, facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    (row,) = await releases_of_team(db_session, team.id)
    assert forced.json()["release_id"] == row.packet["release_id"]
    assert forced.json()["version"] == 1
    assert forced.json()["approved_at"] is not None
    assert forced.json()["forced_at"] is not None
    assert row.session_id == session.id
    assert row.forced_by == facilitator.id
    assert row.packet["check"]["forcedBy"] == facilitator.id
    assert row.packet["check"]["forcedAt"] == forced.json()["forced_at"]
    assert row.packet["check"]["status"] == "forcada"
    assert row.packet["check"]["forced"] is True
    assert row.forced_blockers == ["telling_back_not_checked", "untold_stretch"]
    assert row.packet["check"]["forcedBlockers"] == ["telling_back_not_checked", "untold_stretch"]


async def test_a_passage_with_takes_and_no_telling_back_is_forced_with_no_frases(
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    await rehearsed_session(db_session, project_id=team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    (row,) = await releases_of_team(db_session, team.id)
    assert row.packet["back_translation"]["segments"] == []
    assert row.forced_blockers == ["no_telling_back"]
    assert row.packet["check"]["forcedBlockers"] == ["no_telling_back"]


async def test_a_passage_with_no_rehearsal_take_is_refused_naming_no_rehearsal_audio_and_writes_no_release(  # noqa: E501
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    await a_passage_with_no_rehearsal_take(db_session, team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    refused = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert refused.status_code == 409, refused.text
    assert "no_rehearsal_audio" in refused.json()["detail"]
    assert await releases_of_team(db_session, team.id) == []


async def test_a_consultant_or_a_tablet_cannot_force_a_passage(room, db_session, room_app):
    team, tablet = await a_claimed_device(db_session)
    await a_disputed_passage(db_session, team.id)
    consultant = await make_user(db_session, email="consultora-do-forcar@example.com")
    await grant_room_app_role(db_session, consultant.id, "consultant")
    access, _refresh = await issue_tokens(db_session, consultant)

    by_the_consultant = await room.post(
        desk_passage_release(team.id, P),
        headers={"Authorization": f"Bearer {access}"},
        json=FORCE,
    )
    by_the_tablet = await room.post(
        desk_passage_release(team.id, P), headers=team_headers(tablet), json=FORCE
    )

    assert by_the_consultant.status_code == 403, by_the_consultant.text
    assert by_the_tablet.status_code in (401, 403), by_the_tablet.text
    assert await releases_of_team(db_session, team.id) == []


async def test_a_facilitator_forcing_a_team_they_do_not_facilitate_finds_no_team(
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    await a_disputed_passage(db_session, team.id)
    other_team, _other_tablet = await a_claimed_device(db_session)
    stranger, _ = await at_the_desk(db_session, room_app, other_team)

    refused = await room.post(desk_passage_release(team.id, P), headers=stranger, json=FORCE)

    assert refused.status_code == 404, refused.text
    assert await releases_of_team(db_session, team.id) == []


async def test_two_live_sessions_of_the_passage_only_one_with_takes_releases_that_one(
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    with_takes = await a_disputed_passage(db_session, team.id)
    without_takes = await a_passage_with_no_rehearsal_take(db_session, team.id)
    without_takes.messages = [{"role": "team", "text": "a família saiu de Belém"}]
    await db_session.commit()
    now = datetime.now(UTC)
    await last_active_at(db_session, with_takes, now - timedelta(hours=1))
    await last_active_at(db_session, without_takes, now)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    assert forced.json()["session_id"] == with_takes.id
    (row,) = await releases_of_team(db_session, team.id)
    assert row.session_id == with_takes.id


@pytest.mark.parametrize("most_recently_active", ["first", "second"])
async def test_two_live_sessions_of_the_passage_both_with_takes_release_the_most_recently_active(
    room, db_session, room_app, most_recently_active
):
    team, _tablet = await a_claimed_device(db_session)
    first = await a_disputed_passage(db_session, team.id)
    second = await a_disputed_passage(db_session, team.id)
    newer, older = (first, second) if most_recently_active == "first" else (second, first)
    now = datetime.now(UTC)
    await last_active_at(db_session, older, now - timedelta(hours=1))
    await last_active_at(db_session, newer, now)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    assert forced.json()["session_id"] == newer.id


async def test_the_teams_own_approval_on_the_passage_of_case_1_is_still_refused_with_both_blockers(
    room, db_session
):
    team, tablet = await a_claimed_device(db_session)
    session = await a_disputed_passage(db_session, team.id)

    refused = await room.post(team_release(session.id), headers=team_headers(tablet))

    assert refused.status_code == 200, refused.text
    assert refused.json()["blockers"] == ["telling_back_not_checked", "untold_stretch"]
    assert refused.json()["version"] is None
    assert await releases_of_team(db_session, team.id) == []


async def test_after_a_forced_version_1_the_part_recorded_again_a_clean_check_and_the_teams_approval_record_version_2_conferida_and_version_1_stays_forced(  # noqa: E501
    room, db_session, room_app
):
    team, tablet = await a_claimed_device(db_session)
    session, _take = await rehearsed_session(db_session, project_id=team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)
    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)
    assert forced.status_code == 200, forced.text
    await the_part_recorded_again(db_session, session)
    await reported_playback(db_session, session, await checked_telling_back(db_session, session))

    approved = await room.post(team_release(session.id), headers=team_headers(tablet))

    assert approved.status_code == 200, approved.text
    assert approved.json()["version"] == 2
    first, second = await releases_of_team(db_session, team.id)
    assert first.packet["check"]["status"] == "forcada"
    assert first.packet["check"]["forced"] is True
    assert second.packet["check"]["status"] == "conferida"
    assert second.packet["check"]["forced"] is False


async def test_the_by_session_force_follows_the_same_widened_rule(room, db_session, room_app):
    team, _tablet = await a_claimed_device(db_session)
    session = await a_disputed_passage(db_session, team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_release(session.id), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    (row,) = await releases_of(db_session, session.id)
    assert row.forced_blockers == ["telling_back_not_checked", "untold_stretch"]
    assert row.packet["check"]["status"] == "forcada"


async def test_the_passage_standing_after_a_passage_force_carries_forced_at(
    room, desk_client, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    await a_disputed_passage(db_session, team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)
    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)
    assert forced.status_code == 200, forced.text

    listed = await desk_client.get(f"/api/facilitator/teams/{team.id}/pericopes", headers=desk)

    assert listed.status_code == 200, listed.text
    (passage,) = [entry for entry in listed.json() if entry["pericope"] == P]
    assert passage["release"]["version"] == 1
    assert passage["release"]["forced_at"] is not None


async def test_a_clean_check_with_one_part_not_heard_in_full_is_forced_conferida_with_the_listening_blocker_recorded(  # noqa: E501
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    await a_rehearsal_only_half_heard(db_session, team)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P02), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    (row,) = await releases_of_team(db_session, team.id)
    assert row.packet["check"]["status"] == "conferida"
    assert row.packet["check"]["forced"] is True
    assert row.forced_blockers == ["playback_did_not_cover_the_clip"]
    assert row.packet["check"]["forcedBlockers"] == ["playback_did_not_cover_the_clip"]


async def test_a_release_forced_before_forced_blockers_existed_still_reads_as_forced(
    room, desk_client, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    session = await a_disputed_passage(db_session, team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)
    forced = await room.post(desk_release(session.id), headers=desk, json=FORCE)
    assert forced.status_code == 200, forced.text
    (row,) = await releases_of_team(db_session, team.id)
    added_since = {"forcedBy", "forcedAt", "forcedBlockers"}
    check = {key: value for key, value in row.packet["check"].items() if key not in added_since}
    packet = {**row.packet, "check": check}
    await db_session.execute(
        update(IRRelease).where(IRRelease.id == row.id).values(forced_blockers=None, packet=packet)
    )
    await db_session.commit()

    listed = await desk_client.get(f"/api/facilitator/teams/{team.id}/pericopes", headers=desk)

    (passage,) = [entry for entry in listed.json() if entry["pericope"] == P]
    assert passage["release"]["forced_at"] is not None


async def test_forcing_a_passage_whose_content_was_already_released_returns_that_release(
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    await a_disputed_passage(db_session, team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)
    first = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)
    assert first.status_code == 200, first.text

    again = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert again.status_code == 200, again.text
    assert again.json()["release_id"] == first.json()["release_id"]
    assert again.json()["version"] == 1
    assert len(await releases_of_team(db_session, team.id)) == 1


@pytest.mark.parametrize("body", [{}, {"force": False}])
async def test_a_passage_post_without_force_has_nothing_to_force(room, db_session, room_app, body):
    team, _tablet = await a_claimed_device(db_session)
    await a_disputed_passage(db_session, team.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    refused = await room.post(desk_passage_release(team.id, P), headers=desk, json=body)

    assert refused.status_code == 409, refused.text
    assert await releases_of_team(db_session, team.id) == []


async def test_a_session_archived_by_a_zerar_is_never_the_one_a_passage_force_picks(
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    await a_disputed_passage(db_session, team.id)
    desk, facilitator = await at_the_desk(db_session, room_app, team)
    await archive_pericope(db_session, facilitator, project_id=team.id, pericope=P)

    refused = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert refused.status_code == 409, refused.text
    assert "no_rehearsal_audio" in refused.json()["detail"]
    assert await releases_of_team(db_session, team.id) == []


async def test_after_a_zerar_the_passage_force_releases_the_live_session_and_not_the_archived_one(
    room, db_session, room_app
):
    team, _tablet = await a_claimed_device(db_session)
    archived = await a_disputed_passage(db_session, team.id)
    desk, facilitator = await at_the_desk(db_session, room_app, team)
    await archive_pericope(db_session, facilitator, project_id=team.id, pericope=P)
    live_one = await a_disputed_passage(db_session, team.id)
    now = datetime.now(UTC)
    await last_active_at(db_session, live_one, now - timedelta(hours=1))
    await last_active_at(db_session, archived, now)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    assert forced.json()["session_id"] == live_one.id


async def test_forcing_a_passage_whose_content_the_team_already_released_returns_the_teams_release(
    room, db_session, room_app
):
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    approved = await room.post(team_release(session.id), headers=team_headers(tablet))
    assert approved.status_code == 200, approved.text
    desk, _facilitator = await at_the_desk(db_session, room_app, team)

    forced = await room.post(desk_passage_release(team.id, P), headers=desk, json=FORCE)

    assert forced.status_code == 200, forced.text
    assert forced.json()["release_id"] == approved.json()["release_id"]
    assert forced.json()["version"] == 1
    assert forced.json()["forced_at"] is None
    (row,) = await releases_of_team(db_session, team.id)
    assert row.forced_by is None
    assert row.forced_blockers is None
