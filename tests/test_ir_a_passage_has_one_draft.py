"""ENG-1235 — a passage has one draft, and the session read says whether it is approved.

The draft is the team's live session of the passage (ADR 0071): an approval leaves it open
under its version, and a new take un-approves it. The cases go through the room's own doors
with a real tablet credential and a real facilitator's bearer, and read what a tablet and the
Desk's team card observe.
"""

from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import (
    IRQuestion,
    IRQuestionStatus,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.db.models.project import Project
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.segments import final_segments
from tests.baker import make_app, make_role
from tests.canon_harness import the_canon_moves_on
from tests.opening_harness import (
    Script,
    a_scripted_room,
    desk_routes,
    the_tablet_opens,
)
from tests.release_harness import (
    PREFIX,
    P,
    a_claimed_device,
    at_the_desk,
    checked_telling_back,
    claimed_tablets_of_one_team,
    desk_release,
    ensaio_take,
    ready_session,
    rehearsed_session,
    reported_playback,
    team_headers,
    team_release,
    told_back_with_an_open_finding,
)
from tests.room_harness import (
    heard_every_part,
    rehearsed_in_parts,
    room_client,
    tell_back_about,
    the_bucket_is_in_memory,
    the_room_speaks,
    upload_a_part,
)

TEAMS_URL = "/api/facilitator/teams"


@pytest.fixture()
def script(monkeypatch: pytest.MonkeyPatch) -> Script:
    return a_scripted_room(monkeypatch)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch):
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, bucket, monkeypatch: pytest.MonkeyPatch):
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def desk_client(db_session: AsyncSession, per_request):
    async with desk_routes(db_session, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def zerar(
    client: httpx.AsyncClient, desk: dict[str, str], team_id: str, pericope: str
) -> None:
    answered = await client.post(
        f"{PREFIX}/facilitator/projects/{team_id}/passages/{pericope}/archive", headers=desk
    )
    assert answered.status_code == 200, answered.text[:300]


async def a_retro_take_uploaded(
    client: httpx.AsyncClient, credential: str, session_id: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers=team_headers(credential),
        data={"kind": "retro", "scope": P},
        files={"file": ("retro.m4a", f"retro {uuid.uuid4()}".encode(), "audio/mp4")},
    )


def read_of(session_id: str) -> str:
    return f"{PREFIX}/sessions/{session_id}"


async def the_tablet_reads(client: httpx.AsyncClient, credential: str, session_id: str) -> Any:
    read = await client.get(read_of(session_id), headers=team_headers(credential))
    assert read.status_code == 200, read.text[:300]
    return read.json()


async def approved_by_the_team(
    client: httpx.AsyncClient, credential: str, session_id: str
) -> dict[str, Any]:
    approved = await client.post(team_release(session_id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text[:300]
    assert approved.json()["blockers"] == [], approved.json()
    return approved.json()


async def parts_told_and_played(db: AsyncSession, session: IRSession) -> None:
    told = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=session.pericope,
        findings=[],
        checked=True,
        analysed_segment_ids=[stretch.id for stretch in told],
    )
    report = await heard_every_part(db, session.id)
    await reported_playback(
        db,
        session,
        state,
        played_ranges=report["played_by_take"][0]["played_ranges"],
        clip_duration_ms=report["played_by_take"][0]["clip_duration_ms"],
    )


async def the_takes_the_desk_lists(
    client: httpx.AsyncClient, desk: dict[str, str], session_id: str
) -> list[dict[str, Any]]:
    listed = await client.get(f"{PREFIX}/facilitator/sessions/{session_id}/takes", headers=desk)
    assert listed.status_code == 200, listed.text[:300]
    return listed.json()["takes"]


async def the_teams_card(
    desk_client: httpx.AsyncClient, desk: dict[str, str], team: Project
) -> dict[str, Any]:
    listed = await desk_client.get(TEAMS_URL, headers=desk)
    assert listed.status_code == 200, listed.text[:300]
    (card,) = [card for card in listed.json()["teams"] if card["team_id"] == team.id]
    detail = await desk_client.get(f"{TEAMS_URL}/{team.id}", headers=desk)
    assert detail.status_code == 200, detail.text[:300]
    assert detail.json()["last_activity_at"] == card["last_activity_at"]
    return card


async def a_take_written_on(
    per_request: async_sessionmaker[AsyncSession],
    team: Project,
    session_id: str,
    *,
    at: datetime,
) -> None:
    async with per_request() as fresh:
        fresh.add(
            IRTake(
                session_id=session_id,
                device_id="tablet-1",
                project_id=team.id,
                pericope=P,
                kind=IRTakeKind.ENSAIO,
                scope=P,
                storage_key=f"takes/{session_id}/{uuid.uuid4()}",
                size_bytes=1,
                sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                crc32c="AAAAAAA=",
                content_type="audio/mp4",
                created_at=at,
            )
        )
        await fresh.commit()


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


async def test_a_passage_approved_as_v1_reads_approved_v1_with_the_approvals_name_and_moment_not_forced(  # noqa: E501
    client, db_session
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)

    approval = await approved_by_the_team(client, tablet, session.id)

    read = await the_tablet_reads(client, tablet, session.id)
    assert read["approved"] == {
        "version": 1,
        "release_id": approval["release_id"],
        "approved_at": approval["approved_at"],
        "forced": False,
        "listeners": 0,
    }


async def test_opening_the_approved_passage_again_returns_the_same_draft_still_approved_with_its_telling_back_and_parts(  # noqa: E501
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    desk, _ = await at_the_desk(db_session, room_app, team)
    parts_before = await the_takes_the_desk_lists(client, desk, session.id)
    assert parts_before, "the control: there is a recording to be handed back"
    told_before = (await the_tablet_reads(client, tablet, session.id))["back_translation"]
    assert told_before["segments"], "the control: there is a telling-back to be handed back"
    await approved_by_the_team(client, tablet, session.id)

    reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": session.language})

    assert reopened["session_id"] == session.id
    assert reopened["approved"]["version"] == 1
    assert reopened["back_translation"]["segments"] == told_before["segments"]
    assert await the_takes_the_desk_lists(client, desk, reopened["session_id"]) == parts_before


async def test_a_draft_never_approved_reads_no_approval(client, db_session) -> None:
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)

    read = await the_tablet_reads(client, tablet, session.id)

    assert read["approved"] is None


async def test_a_facilitators_forced_approval_reads_forced(client, db_session, room_app) -> None:
    team, tablet = await a_claimed_device(db_session)
    session, _take = await rehearsed_session(db_session, project_id=team.id)
    await reported_playback(
        db_session, session, await told_back_with_an_open_finding(db_session, session)
    )
    desk, _ = await at_the_desk(db_session, room_app, team)
    refused = await client.post(team_release(session.id), headers=team_headers(tablet))
    assert refused.json()["blockers"] == ["telling_back_not_checked"], (
        "the control: a finding is open"
    )

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert forced.status_code == 200, forced.text
    read = await the_tablet_reads(client, tablet, session.id)
    assert read["approved"]["forced"] is True
    assert read["approved"]["version"] == forced.json()["version"]


async def test_a_part_recorded_again_after_approval_un_approves_the_draft_and_the_next_approval_is_v2(  # noqa: E501
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session, parts = await rehearsed_in_parts(db_session, 3, project_id=team.id)
    await parts_told_and_played(db_session, session)
    first = await approved_by_the_team(client, tablet, session.id)
    assert first["version"] == 1
    assert (await the_tablet_reads(client, tablet, session.id))["approved"]["version"] == 1

    again = await upload_a_part(
        client,
        session.id,
        part=2,
        audio=b"the second part, recorded again",
        headers=team_headers(tablet),
    )
    assert again.status_code == 200, again.text[:300]

    read = await the_tablet_reads(client, tablet, session.id)
    assert read["approved"] is None
    by_part: dict[int, list[str]] = {}
    for take in await the_takes_the_desk_lists(client, desk, session.id):
        by_part.setdefault(take["ordinal"], []).append(take["take_id"])
    assert (by_part[1], by_part[3]) == ([parts[0].id], [parts[2].id])
    fresh = await db_session.get(IRTake, again.json()["take_id"])
    await db_session.refresh(session)
    await tell_back_about(db_session, session, fresh)
    await parts_told_and_played(db_session, session)
    second = await approved_by_the_team(client, tablet, session.id)
    assert second["version"] == 2
    assert (await the_tablet_reads(client, tablet, session.id))["approved"]["version"] == 2


async def test_a_draft_another_languages_approval_moved_past_is_no_longer_approved(
    client, db_session
) -> None:
    team, tablet = await a_claimed_device(db_session)
    in_portuguese, _ = await rehearsed_session(db_session, project_id=team.id, language="pt")
    await reported_playback(
        db_session, in_portuguese, await checked_telling_back(db_session, in_portuguese)
    )
    in_english, _ = await rehearsed_session(db_session, project_id=team.id, language="en")
    await reported_playback(
        db_session, in_english, await checked_telling_back(db_session, in_english)
    )
    assert (await approved_by_the_team(client, tablet, in_portuguese.id))["version"] == 1
    assert (await the_tablet_reads(client, tablet, in_portuguese.id))["approved"]["version"] == 1

    assert (await approved_by_the_team(client, tablet, in_english.id))["version"] == 2

    assert (await the_tablet_reads(client, tablet, in_portuguese.id))["approved"] is None
    assert (await the_tablet_reads(client, tablet, in_english.id))["approved"]["version"] == 2


async def test_a_second_tablets_take_lands_in_the_one_draft(
    client, db_session, script, room_app
) -> None:
    team, _user, (first, second) = await claimed_tablets_of_one_team(
        db_session, email="fac@example.com", tablets=2
    )
    desk, _ = await at_the_desk(db_session, room_app, team)

    opened_by_first = await the_tablet_opens(
        client, first.credential, {"pericope": P, "language": "pt"}
    )
    opened_by_second = await the_tablet_opens(
        client, second.credential, {"pericope": P, "language": "pt"}
    )
    uploaded = await upload_a_part(
        client,
        opened_by_second["session_id"],
        part=1,
        audio=b"the second tablet's part",
        headers=team_headers(second.credential),
    )

    assert opened_by_first["session_id"] == opened_by_second["session_id"]
    assert uploaded.status_code == 200, uploaded.text[:300]
    listed = await client.get(
        f"{PREFIX}/facilitator/sessions/{opened_by_first['session_id']}/takes", headers=desk
    )
    assert [take["take_id"] for take in listed.json()["takes"]] == [uploaded.json()["take_id"]]


async def test_a_panorama_session_has_no_draft(client, db_session, script) -> None:
    _team, tablet = await a_claimed_device(db_session)
    opened = await the_tablet_opens(client, tablet, {"pericope": "OV-Ruth", "language": "pt"})

    read = await the_tablet_reads(client, tablet, opened["session_id"])
    approval = await client.post(team_release(opened["session_id"]), headers=team_headers(tablet))

    assert read["approved"] is None
    assert approval.json()["blockers"] == ["panorama_sessions_never_release"]


async def test_a_part_recorded_again_keeps_the_take_it_replaced(
    client, db_session, room_app
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session, parts = await rehearsed_in_parts(db_session, 3, project_id=team.id)
    desk, _ = await at_the_desk(db_session, room_app, team)

    again = await upload_a_part(
        client,
        session.id,
        part=2,
        audio=b"the second part, recorded again",
        headers=team_headers(tablet),
    )

    assert again.status_code == 200, again.text[:300]
    listed = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/takes", headers=desk)
    second_part = [take["take_id"] for take in listed.json()["takes"] if take["ordinal"] == 2]
    assert sorted(second_part) == sorted([parts[1].id, again.json()["take_id"]])


async def test_a_passage_zeroed_after_v1_and_approved_again_is_v2_and_its_new_draft_reads_no_approval_until_then(  # noqa: E501
    client, db_session, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    archived = await ready_session(db_session, project_id=team.id)
    await approved_by_the_team(client, tablet, archived.id)

    await zerar(client, desk, team.id, P)
    reopened = await the_tablet_opens(
        client, tablet, {"pericope": P, "language": archived.language}
    )

    assert reopened["session_id"] != archived.id
    assert reopened["approved"] is None
    new_session = await db_session.get(IRSession, reopened["session_id"])
    await db_session.refresh(new_session)
    await rehearsed_take_for(db_session, new_session)
    await reported_playback(
        db_session, new_session, await checked_telling_back(db_session, new_session)
    )
    assert (await approved_by_the_team(client, tablet, new_session.id))["version"] == 2
    assert (await the_tablet_reads(client, tablet, new_session.id))["approved"]["version"] == 2


async def rehearsed_take_for(db: AsyncSession, session: IRSession) -> IRTake:
    take = ensaio_take(session.id, project_id=session.project_id)
    db.add(take)
    session.coverage_state = merge(
        initial_state(session.pericope), pericope_num=session.pericope, engaged=element_keys(P)
    )
    await db.commit()
    return take


async def test_a_team_whose_only_work_was_zeroed_shows_no_last_activity(
    client, desk_client, db_session, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    uploaded = await a_retro_take_uploaded(client, tablet, opened["session_id"])
    assert uploaded.status_code == 200, uploaded.text[:300]
    assert (await the_teams_card(desk_client, desk, team))["last_activity_at"] is not None

    await zerar(client, desk, team.id, P)

    assert (await the_teams_card(desk_client, desk, team))["last_activity_at"] is None


async def test_a_take_landing_on_a_zeroed_session_after_the_zerar_is_not_the_teams_activity(
    client, desk_client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await zerar(client, desk, team.id, P)

    await a_take_written_on(
        per_request, team, opened["session_id"], at=datetime.now(UTC) + timedelta(seconds=5)
    )

    assert (await the_teams_card(desk_client, desk, team))["last_activity_at"] is None


async def test_live_work_after_a_zerar_is_the_teams_last_activity(
    client, desk_client, db_session, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    first = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    assert (await a_retro_take_uploaded(client, tablet, first["session_id"])).status_code == 200
    await zerar(client, desk, team.id, P)
    after_the_zerar = datetime.now(UTC).replace(microsecond=0)
    assert (await the_teams_card(desk_client, desk, team))["last_activity_at"] is None

    again = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    assert (await a_retro_take_uploaded(client, tablet, again["session_id"])).status_code == 200

    last = moment((await the_teams_card(desk_client, desk, team))["last_activity_at"])
    assert last >= after_the_zerar


async def test_a_raised_hand_asked_before_a_zerar_still_counts_as_the_teams_activity(
    client, desk_client, db_session, per_request, room_app, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    asked_at = datetime.now(UTC).replace(microsecond=0) - timedelta(days=3)
    async with per_request() as fresh:
        fresh.add(
            IRQuestion(
                session_id=opened["session_id"],
                device_id="tablet-1",
                project_id=team.id,
                pericope=P,
                status=IRQuestionStatus.OPEN,
                audio_key="internalization-room/questions/mao-levantada.m4a",
                created_at=asked_at,
            )
        )
        await fresh.commit()

    await zerar(client, desk, team.id, P)

    card = await the_teams_card(desk_client, desk, team)
    assert moment(card["last_activity_at"]) == asked_at


async def test_a_take_naming_no_session_still_counts_as_the_teams_activity(
    desk_client, db_session, per_request, room_app
) -> None:
    team, _tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    written_at = datetime.now(UTC).replace(microsecond=0) - timedelta(days=2)

    await a_take_written_on(per_request, team, "nenhuma-sessao-deste-teste", at=written_at)

    card = await the_teams_card(desk_client, desk, team)
    assert moment(card["last_activity_at"]) == written_at


async def test_a_demo_team_that_approved_before_being_marked_still_reads_and_opens_with_no_approval(
    client, db_session, script
) -> None:
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved_by_the_team(client, tablet, session.id)
    team.is_demo_team = True
    await db_session.commit()

    read = await client.get(read_of(session.id), headers=team_headers(tablet))
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"pericope": P, "language": session.language},
    )

    assert (read.status_code, opened.status_code) == (200, 200), (read.text, opened.text)
    assert read.json()["approved"] is None
    assert opened.json()["approved"] is None


async def test_asking_whether_a_draft_is_approved_reads_no_canon_so_one_that_is_gone_changes_nothing(  # noqa: E501
    client, db_session, monkeypatch, tmp_path: Path
) -> None:
    """The approval is a comparison of takes (ADR 0081): nothing is composed to answer it."""
    team, tablet = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=team.id)
    await approved_by_the_team(client, tablet, session.id)
    shutil.rmtree(the_canon_moves_on(monkeypatch, tmp_path, "a" * 40))

    approved = await approved_draft(db_session, session)

    assert approved is not None
    assert approved.version == 1


async def test_a_raised_hand_answered_after_approval_leaves_the_draft_approved_as_v1(
    client, db_session, room_app
) -> None:
    """ENG-1260 (ENG-1256, acceptance 1): only a change of takes re-opens an approved draft."""
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session, _parts = await rehearsed_in_parts(db_session, 2, project_id=team.id)
    hand = IRQuestion(
        session_id=session.id,
        device_id="tablet-1",
        project_id=team.id,
        pericope=session.pericope,
        status=IRQuestionStatus.OPEN,
        audio_key="internalization-room/questions/mao-levantada.m4a",
    )
    db_session.add(hand)
    await db_session.commit()
    await parts_told_and_played(db_session, session)
    assert (await approved_by_the_team(client, tablet, session.id))["version"] == 1

    answered = await client.post(f"{PREFIX}/facilitator/questions/{hand.id}/resolve", headers=desk)
    assert answered.status_code == 200, answered.text[:300]

    assert (await the_tablet_reads(client, tablet, session.id))["approved"]["version"] == 1
    assert (await approved_by_the_team(client, tablet, session.id))["version"] == 1


async def test_a_frase_translated_again_after_approval_leaves_the_draft_approved_as_v1(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ENG-1260 (ENG-1256, acceptance 2)."""

    async def said(*_: Any, **__: Any) -> str:
        return "Noemi voltou com Rute para Belém"

    monkeypatch.setattr(segments_api, "heard", said)
    team, tablet = await a_claimed_device(db_session)
    session, _parts = await rehearsed_in_parts(db_session, 2, project_id=team.id)
    await parts_told_and_played(db_session, session)
    assert (await approved_by_the_team(client, tablet, session.id))["version"] == 1
    frase = (await final_segments(db_session, session.id))[0]

    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{frase.id}/replace",
        headers=team_headers(tablet),
        data={
            "take_id": frase.take_id,
            "starts_ms": str(frase.starts_ms),
            "ends_ms": str(frase.ends_ms),
        },
        files={"file": ("trecho.m4a", b"a equipe traduziu a frase de novo", "audio/mp4")},
    )
    assert told.status_code == 200, told.text[:300]

    assert (await the_tablet_reads(client, tablet, session.id))["approved"]["version"] == 1


async def test_the_release_door_serves_v1s_stored_packet_after_a_hand_is_answered(
    client, db_session, room_app
) -> None:
    """A release id names exactly its stored packet while the takes are its own."""
    team, tablet = await a_claimed_device(db_session)
    desk, _ = await at_the_desk(db_session, room_app, team)
    session, _parts = await rehearsed_in_parts(db_session, 2, project_id=team.id)
    hand = IRQuestion(
        session_id=session.id,
        device_id="tablet-1",
        project_id=team.id,
        pericope=session.pericope,
        status=IRQuestionStatus.OPEN,
        audio_key="internalization-room/questions/mao-levantada.m4a",
    )
    db_session.add(hand)
    await db_session.commit()
    await parts_told_and_played(db_session, session)
    await approved_by_the_team(client, tablet, session.id)
    answered = await client.post(f"{PREFIX}/facilitator/questions/{hand.id}/resolve", headers=desk)
    assert answered.status_code == 200, answered.text[:300]

    live = await client.get(desk_release(session.id), headers=desk)
    stored = await client.get(
        f"{PREFIX}/facilitator/sessions/{session.id}/releases/1", headers=desk
    )

    assert live.status_code == 200, live.text[:300]
    assert live.json()["version"] == 1
    assert live.json()["package_sha256"] == stored.json()["package_sha256"]
    assert live.json()["raised_questions"] == stored.json()["raised_questions"]


async def test_the_translation_started_over_after_approval_leaves_the_draft_approved_as_v1(
    client, db_session
) -> None:
    """ENG-1260 (Q64): the Restart changes no take."""
    team, tablet = await a_claimed_device(db_session)
    session, _parts = await rehearsed_in_parts(db_session, 2, project_id=team.id)
    await parts_told_and_played(db_session, session)
    assert (await approved_by_the_team(client, tablet, session.id))["version"] == 1

    restarted = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/restart", headers=team_headers(tablet)
    )
    assert restarted.status_code == 200, restarted.text[:300]

    assert (await the_tablet_reads(client, tablet, session.id))["approved"]["version"] == 1
