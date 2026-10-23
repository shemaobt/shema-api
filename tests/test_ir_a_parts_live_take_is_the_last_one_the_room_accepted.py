"""ENG-1760 — a part's live take is the last one the room accepted, so a reinstall never hides it.

A reinstalled tablet, or a second one, counts its passes from 1 again, so the pass the tablet
sends no longer says which recording of a part came last, and a tablet's clock can read any year.
Under one part number the take the room accepts last is the part, whatever its pass or its
**Recording time**. Every case sends real WAV through the room's doors and reads which take is
the part where the Desk, the tablet, the consultant and the **Packet** read it. Expected values
come from the ticket as settled on 2026-10-23 (recon Q69).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.core.config import get_settings
from app.db.models.auth import App
from app.db.models.internalization_room import IRSceneRehearsal, IRSegment, IRSession
from app.models.internalization_room import PlayedTake
from app.services.internalization_room import report_playback
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.approved_draft import standing_approvals
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
)
from app.services.internalization_room.release import approve_release
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import get_session, save_back_translation
from tests.baker import grant_room_app_role, make_app, make_role, make_user
from tests.hard_stretch_harness import MemoryStore
from tests.opening_harness import desk_routes
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    TABLET,
    P,
    a_claimed_device,
    at_the_desk,
    ensaio_take,
    reported_playback,
    team_headers,
    team_release,
)
from tests.room_harness import (
    nothing_is_read_ahead,
    release_blockers,
    release_packet,
    room_client,
    stored_telling_back,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.scene_rehearsal_harness import recording
from tests.sentence_harness import re_record, spoken

BUCKET = "balde-de-teste"
RELEASE_V1 = "internalize-terena-p03-v1"
MONDAY = "2026-10-19T10:00:00+00:00"
TUESDAY = "2026-10-20T10:00:00+00:00"
OLD_TABLET = "tablet-antes-de-reinstalar"
NEW_TABLET = "tablet-reinstalado"


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    nothing_is_read_ahead(monkeypatch)

    async def said(*_: Any, **__: Any) -> str:
        return "a equipe contou o trecho de volta"

    monkeypatch.setattr(bt_api, "heard", said)
    monkeypatch.setattr(segments_api, "heard", said)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", BUCKET, raising=False)

    async def _signed(
        bucket: str,
        key: str,
        *,
        expiry_minutes: int,
        response_content_type: str | None = None,
        response_disposition: str | None = None,
    ) -> str:
        return (
            f"https://storage.test/{bucket}/{key}"
            f"?X-Goog-Expires={expiry_minutes * 60}"
            f"&response-content-disposition={quote(response_disposition or '')}"
        )

    monkeypatch.setattr(takes_service, "generate_signed_download_url", _signed)
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def desk_client(db_session: AsyncSession):
    async with desk_routes(db_session) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession) -> App:
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
async def consultant(db_session: AsyncSession) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
async def team(db_session: AsyncSession) -> tuple[Any, str]:
    return await a_claimed_device(db_session, language_name="Terena")


@pytest.fixture()
async def session(db_session: AsyncSession, team: tuple[Any, str]) -> IRSession:
    from app.services.internalization_room.sessions import create_session

    project, _credential = team
    return await create_session(db_session, pericope=P, project_id=project.id, language="pt")


def an_hour_ago() -> str:
    return (datetime.now(UTC) - timedelta(hours=1)).isoformat()


async def a_beat() -> None:
    await asyncio.sleep(0.01)


async def send(
    client: httpx.AsyncClient,
    credential: str,
    session_id: str,
    audio: bytes,
    *,
    part: int = 1,
    tablet: str = TABLET,
    **fields: object,
) -> dict[str, Any]:
    """A part sent up the way the tablet sends it, with whichever of its values the case names."""
    data = {"kind": "ensaio", "scope": f"parte-{part}", "chunk_index": str(part)}
    data |= {name: str(value) for name, value in fields.items()}
    answer = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers=team_headers(credential) | {"X-Room-Device": tablet},
        data=data,
        files={"file": ("gravacao.wav", audio, "audio/wav")},
    )
    assert answer.status_code == 200, answer.text
    await a_beat()
    return answer.json()


async def read_downloads(
    client: httpx.AsyncClient, desk: dict[str, str], session_id: str
) -> dict[str, Any]:
    answer = await client.get(
        f"{PREFIX}/facilitator/sessions/{session_id}/takes/downloads", headers=desk
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


async def tablet_list(
    client: httpx.AsyncClient, credential: str, session_id: str
) -> list[dict[str, Any]]:
    answer = await client.get(
        f"{PREFIX}/sessions/{session_id}/takes", headers=team_headers(credential)
    )
    assert answer.status_code == 200, answer.text
    return answer.json()["takes"]


def the_tablets_part(listed: list[dict[str, Any]], ordinal: int = 1) -> str:
    """The tablet's own rule on resume: the last recording under each number, as listed."""
    under = [take for take in listed if take["kind"] == "ensaio" and take["ordinal"] == ordinal]
    return under[-1]["take_id"]


async def the_desks_part(
    client: httpx.AsyncClient, db: AsyncSession, room_app: App, project: Any, session_id: str
) -> str:
    desk, _user = await at_the_desk(db, room_app, project)
    [live] = (await read_downloads(client, desk, session_id))["takes"]
    return live["take_id"]


async def a_scene_rehearsal(db: AsyncSession, session: IRSession) -> IRSceneRehearsal:
    rehearsal = IRSceneRehearsal(
        session_id=session.id,
        project_id=session.project_id,
        pericope=session.pericope,
        n=1,
        device_id=TABLET,
        storage_key=f"scene-rehearsals/{session.id}/1",
        size_bytes=2048,
        sha256="p" * 64,
        crc32c="AAAAAAA=",
        content_type="audio/wav",
        duration_ms=4000,
        scene="S1",
    )
    db.add(rehearsal)
    await db.commit()
    return rehearsal


async def told_back_whole(db: AsyncSession, session: IRSession, take_id: str) -> IRSegment:
    return await capture_segment(
        db,
        session,
        take_id=take_id,
        starts_ms=0,
        ends_ms=1000,
        bridge_take_id="retro-1",
        transcript="a parte contada de volta",
    )


async def checked_over(db: AsyncSession, session: IRSession, told: list[IRSegment]) -> None:
    state = BackTranslationState(
        scope=P, findings=[], checked=True, analysed_segment_ids=[stretch.id for stretch in told]
    )
    await reported_playback(db, session, state)


async def a_checked_telling(db: AsyncSession, session: IRSession) -> None:
    await checked_over(db, session, await final_segments(db, session.id))


async def told_while_the_order_was_the_pass(
    client: httpx.AsyncClient, credential: str, session: IRSession, db: AsyncSession
) -> tuple[dict[str, Any], IRSegment]:
    """A part stored before ENG-1760: pass 2, then pass 1 from a reinstall landing after it.

    The pass then chose pass 2 as the part, so it was told back over it, and those rows are
    still stored when the room starts reading by arrival.
    """
    monday = await send(
        client, credential, session.id, recording(2, 1), tablet=OLD_TABLET, pass_number=2
    )
    tuesday = await send(
        client, credential, session.id, recording(2, 2), tablet=NEW_TABLET, pass_number=1
    )
    return tuesday, await told_back_whole(db, session, monday["take_id"])


async def recorded_on_monday(
    client: httpx.AsyncClient, credential: str, session: IRSession
) -> dict[str, Any]:
    return await send(
        client,
        credential,
        session.id,
        recording(2, 1),
        tablet=OLD_TABLET,
        pass_number=2,
        recorded_at=MONDAY,
    )


async def recorded_again_on_tuesday_after_a_reinstall(
    client: httpx.AsyncClient, credential: str, session: IRSession
) -> dict[str, Any]:
    return await send(
        client,
        credential,
        session.id,
        recording(2, 2),
        tablet=NEW_TABLET,
        pass_number=1,
        recorded_at=TUESDAY,
    )


async def recorded_on_monday_then_again_on_tuesday_after_a_reinstall(
    client: httpx.AsyncClient, credential: str, session: IRSession
) -> tuple[dict[str, Any], dict[str, Any]]:
    monday = await recorded_on_monday(client, credential, session)
    tuesday = await recorded_again_on_tuesday_after_a_reinstall(client, credential, session)
    return monday, tuesday


async def test_a_part_recorded_again_on_a_reinstalled_tablet_is_the_part_although_its_pass_is_lower(
    client, db_session, room_app, team, session
):
    project, credential = team
    monday, tuesday = await recorded_on_monday_then_again_on_tuesday_after_a_reinstall(
        client, credential, session
    )
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert [(each["take_id"], each["filename"]) for each in listed["takes"]] == [
        (tuesday["take_id"], f"{RELEASE_V1}-S1.wav")
    ]
    assert [(each["take_id"], each["filename"]) for each in listed["superseded_takes"]] == [
        (monday["take_id"], f"{RELEASE_V1}-S1-substituida-{monday['take_id']}.wav")
    ]


async def test_a_take_that_arrives_later_is_the_part_whatever_its_recording_time_or_pass(
    client, db_session, room_app, team, session
):
    project, credential = team
    await recorded_again_on_tuesday_after_a_reinstall(client, credential, session)
    monday = await recorded_on_monday(client, credential, session)

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id) == monday["take_id"]
    )
    assert the_tablets_part(await tablet_list(client, credential, session.id)) == monday["take_id"]


async def test_of_two_takes_with_the_same_recording_time_the_later_arrival_is_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    await send(client, credential, session.id, recording(2, 1), pass_number=2, recorded_at=TUESDAY)
    later = await send(
        client, credential, session.id, recording(2, 2), pass_number=1, recorded_at=TUESDAY
    )

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id) == later["take_id"]
    )


async def test_of_two_takes_sent_with_no_recording_time_the_later_arrival_is_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    await send(client, credential, session.id, recording(2, 1), pass_number=2)
    later = await send(client, credential, session.id, recording(2, 2), pass_number=1)

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id) == later["take_id"]
    )


async def test_a_live_take_whose_clock_reads_2099_is_replaced_by_the_take_recorded_today(
    client, db_session, room_app, team, session
):
    project, credential = team
    await send(
        client, credential, session.id, recording(2, 1), recorded_at="2099-01-01T10:00:00+00:00"
    )
    today = await send(client, credential, session.id, recording(2, 2), recorded_at=an_hour_ago())

    listed = await tablet_list(client, credential, session.id)
    assert (
        await the_desks_part(client, db_session, room_app, project, session.id) == today["take_id"]
    )
    assert the_tablets_part(listed) == today["take_id"]
    assert [take["recorded_at"] for take in listed] == [
        "2099-01-01T10:00:00+00:00",
        today["recorded_at"],
    ]


async def test_a_take_whose_clock_reads_2000_landing_last_is_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    await send(client, credential, session.id, recording(2, 1), recorded_at=an_hour_ago())
    stale_clock = await send(
        client, credential, session.id, recording(2, 2), recorded_at="2000-01-01T10:00:00+00:00"
    )

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id)
        == stale_clock["take_id"]
    )
    assert (
        the_tablets_part(await tablet_list(client, credential, session.id))
        == stale_clock["take_id"]
    )


async def test_a_part_joined_after_a_take_was_recorded_is_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    before = await send(
        client, credential, session.id, recording(2, 1), pass_number=1, recorded_at=an_hour_ago()
    )
    origin = await a_scene_rehearsal(db_session, session)
    joined = await send(
        client,
        credential,
        session.id,
        recording(2, 2),
        pass_number=1,
        origin=origin.id,
        over_take=before["take_id"],
    )

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id) == joined["take_id"]
    )


async def test_a_sentence_laid_into_a_part_lands_the_spliced_take_as_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    part = await send(
        client, credential, session.id, recording(4, 21), pass_number=1, recorded_at=an_hour_ago()
    )
    first = await capture_segment(
        db_session,
        session,
        take_id=part["take_id"],
        starts_ms=0,
        ends_ms=2000,
        bridge_take_id="retro-1",
        transcript="a primeira frase",
    )
    await capture_segment(
        db_session,
        session,
        take_id=part["take_id"],
        starts_ms=2000,
        ends_ms=4000,
        bridge_take_id="retro-2",
        transcript="a segunda frase",
    )

    laid = await re_record(
        client, session.id, first.id, spoken(1.0), headers=team_headers(credential)
    )

    assert laid.status_code == 200, laid.text
    spliced = laid.json()["segments"][0]["take_id"]
    assert spliced != part["take_id"]
    assert await the_desks_part(client, db_session, room_app, project, session.id) == spliced
    assert the_tablets_part(await tablet_list(client, credential, session.id)) == spliced


async def test_a_spliced_part_timed_on_the_tablet_stands_approved_for_the_team_menu_and_the_desk(
    client, desk_client, db_session, team, session, room_app
):
    project, credential = team
    part = await send(
        client, credential, session.id, recording(4, 21), pass_number=1, recorded_at=an_hour_ago()
    )
    first = await capture_segment(
        db_session,
        session,
        take_id=part["take_id"],
        starts_ms=0,
        ends_ms=4000,
        bridge_take_id="retro-1",
        transcript="a primeira frase",
    )
    laid = await re_record(
        client, session.id, first.id, spoken(1.0), headers=team_headers(credential)
    )
    assert laid.status_code == 200, laid.text
    sentence = laid.json()["segments"][0]
    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{first.id}/replace",
        headers=team_headers(credential),
        data={
            "take_id": sentence["take_id"],
            "starts_ms": str(sentence["starts_ms"]),
            "ends_ms": str(sentence["ends_ms"]),
        },
        files={"file": ("trecho.m4a", b"a equipe traduziu a frase nova", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    state = await stored_telling_back(db_session, session)
    told_stretches = await final_segments(db_session, session.id)
    state.checked = True
    state.analysed_segment_ids = [stretch.id for stretch in told_stretches]
    await reported_playback(db_session, session, state)

    approved = await client.post(team_release(session.id), headers=team_headers(credential))

    assert approved.status_code == 200, approved.text
    assert approved.json()["blockers"] == []
    assert await standing_approvals(db_session, project.id) == {P}
    menu = await client.get(
        f"{PREFIX}/books/Ruth/passages?language=pt", headers=team_headers(credential)
    )
    assert {entry["pericope"]: entry["approved"] for entry in menu.json()["passages"]}[P] is True
    desk, _user = await at_the_desk(db_session, room_app, project)
    detail = await desk_client.get(f"/api/facilitator/teams/{project.id}", headers=desk)
    assert detail.json()["approved_total"] == 1


async def test_a_part_recorded_again_after_a_splice_is_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    part = await send(client, credential, session.id, recording(4, 21), pass_number=1)
    first = await capture_segment(
        db_session,
        session,
        take_id=part["take_id"],
        starts_ms=0,
        ends_ms=2000,
        bridge_take_id="retro-1",
        transcript="a primeira frase",
    )
    laid = await re_record(
        client, session.id, first.id, spoken(1.0), headers=team_headers(credential)
    )
    assert laid.status_code == 200, laid.text

    again = await send(client, credential, session.id, recording(4, 22), pass_number=2)

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id) == again["take_id"]
    )
    assert the_tablets_part(await tablet_list(client, credential, session.id)) == again["take_id"]


async def test_every_reader_names_the_same_take_as_the_part(
    client, db_session, room_app, team, session, consultant
):
    project, credential = team
    _monday, tuesday = await recorded_on_monday_then_again_on_tuesday_after_a_reinstall(
        client, credential, session
    )
    await told_back_whole(db_session, session, tuesday["take_id"])
    await a_checked_telling(db_session, session)

    approved = await client.post(team_release(session.id), headers=team_headers(credential))

    assert approved.status_code == 200, approved.text
    packet = await release_packet(db_session, session)
    assert [take["take_id"] for take in packet["audio"]["rehearsal_takes"]] == [tuesday["take_id"]]
    assert (
        await the_desks_part(client, db_session, room_app, project, session.id)
        == tuesday["take_id"]
    )
    assert the_tablets_part(await tablet_list(client, credential, session.id)) == tuesday["take_id"]
    read = await client.get(
        f"{PREFIX}/facilitator/sessions/{session.id}/mother-tongue-takes", headers=consultant
    )
    assert read.status_code == 200, read.text
    assert [take["take_id"] for take in read.json()["takes"]] == [tuesday["take_id"]]


async def test_the_tablets_list_carries_each_takes_pass_as_sent(client, team, session):
    _project, credential = team
    monday, tuesday = await recorded_on_monday_then_again_on_tuesday_after_a_reinstall(
        client, credential, session
    )

    listed = await tablet_list(client, credential, session.id)

    passes = {take["take_id"]: take["pass_number"] for take in listed}
    assert passes == {monday["take_id"]: 2, tuesday["take_id"]: 1}


async def test_takes_stored_before_this_change_keep_their_arrival_order(
    client, db_session, team, session
):
    project, credential = team
    arrived_first = ensaio_take(
        session.id,
        scope="parte-1",
        ordinal=1,
        pass_number=2,
        sha256="m" * 64,
        project_id=project.id,
        created_at=datetime(2026, 10, 20, 9, 0, tzinfo=UTC),
    )
    arrived_first.recorded_at = datetime.fromisoformat(TUESDAY)
    arrived_last = ensaio_take(
        session.id,
        scope="parte-1",
        ordinal=1,
        pass_number=1,
        sha256="t" * 64,
        project_id=project.id,
        created_at=datetime(2026, 10, 20, 11, 0, tzinfo=UTC),
    )
    arrived_last.recorded_at = datetime.fromisoformat(MONDAY)
    db_session.add_all([arrived_last, arrived_first])
    await db_session.commit()

    assert the_tablets_part(await tablet_list(client, credential, session.id)) == arrived_last.id


async def test_two_takes_stored_at_the_same_instant_are_read_by_their_id(
    client, db_session, team, session
):
    project, credential = team
    landed = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    first_by_id, last_by_id = (
        ensaio_take(
            session.id,
            scope="parte-1",
            ordinal=1,
            sha256=sha * 64,
            project_id=project.id,
            created_at=landed,
        )
        for sha in "ab"
    )
    first_by_id.id = "00000000-0000-4000-8000-000000000001"
    last_by_id.id = "00000000-0000-4000-8000-000000000002"
    db_session.add(last_by_id)
    await db_session.commit()
    db_session.add(first_by_id)
    await db_session.commit()

    assert the_tablets_part(await tablet_list(client, credential, session.id)) == last_by_id.id


async def test_a_part_stored_under_the_pass_order_is_not_told_by_the_take_it_no_longer_is(
    client, db_session, team, session
):
    _project, credential = team
    tuesday, over_monday = await told_while_the_order_was_the_pass(
        client, credential, session, db_session
    )
    await checked_over(db_session, session, [over_monday])
    await report_playback(
        db_session,
        session,
        await stored_telling_back(db_session, session),
        played_by_take=[
            PlayedTake(take_id=tuesday["take_id"], played_ranges=[[0, 2000]], clip_duration_ms=2000)
        ],
        played_ranges=[[0, 2000]],
        clip_duration_ms=2000,
    )

    pressed = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/finish",
        headers=team_headers(credential),
    )
    approved = await client.post(team_release(session.id), headers=team_headers(credential))

    assert the_tablets_part(await tablet_list(client, credential, session.id)) == tuesday["take_id"]
    assert pressed.status_code == 200, pressed.text
    assert pressed.json()["refusal"] == "NOTHING_TRANSLATED"
    assert approved.status_code == 200, approved.text
    assert "no_telling_back" in approved.json()["blockers"]
    assert "no_telling_back" in await release_blockers(db_session, session)


async def test_a_check_stored_under_the_pass_order_goes_stale_when_arrival_changes_the_part(
    client, db_session, team, session
):
    _project, credential = team
    tuesday, over_monday = await told_while_the_order_was_the_pass(
        client, credential, session, db_session
    )
    second = await send(client, credential, session.id, recording(2, 3), part=2, pass_number=1)
    over_second = await told_back_whole(db_session, session, second["take_id"])
    await checked_over(db_session, session, [over_monday, over_second])

    stale = await client.post(team_release(session.id), headers=team_headers(credential))
    await told_back_whole(db_session, session, tuesday["take_id"])
    await a_checked_telling(db_session, session)
    approved = await client.post(team_release(session.id), headers=team_headers(credential))

    assert stale.status_code == 200, stale.text
    assert "telling_back_not_checked" in stale.json()["blockers"]
    assert approved.status_code == 200, approved.text
    assert approved.json()["blockers"] == []


async def test_a_sentence_laid_again_over_a_spliced_part_keeps_the_newest_splice_as_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    part = await send(
        client, credential, session.id, recording(4, 21), pass_number=1, recorded_at=an_hour_ago()
    )
    first = await capture_segment(
        db_session,
        session,
        take_id=part["take_id"],
        starts_ms=0,
        ends_ms=2000,
        bridge_take_id="retro-1",
        transcript="a primeira frase",
    )
    await capture_segment(
        db_session,
        session,
        take_id=part["take_id"],
        starts_ms=2000,
        ends_ms=4000,
        bridge_take_id="retro-2",
        transcript="a segunda frase",
    )
    once = await re_record(
        client,
        session.id,
        first.id,
        spoken(1.0),
        sentence_id="sentence-0001",
        headers=team_headers(credential),
    )
    assert once.status_code == 200, once.text

    again = await re_record(
        client,
        session.id,
        first.id,
        spoken(0.5),
        sentence_id="sentence-0002",
        headers=team_headers(credential),
    )

    assert again.status_code == 200, again.text
    spliced_again = again.json()["segments"][0]["take_id"]
    assert spliced_again not in (part["take_id"], once.json()["segments"][0]["take_id"])
    assert await the_desks_part(client, db_session, room_app, project, session.id) == spliced_again
    assert the_tablets_part(await tablet_list(client, credential, session.id)) == spliced_again


async def test_a_forced_release_carries_no_finding_on_the_take_that_is_no_longer_the_part(
    client, db_session, team, session
):
    _project, credential = team
    _tuesday, over_monday = await told_while_the_order_was_the_pass(
        client, credential, session, db_session
    )
    await checked_over(db_session, session, [over_monday])
    state = await stored_telling_back(db_session, session)
    state.findings = [
        Finding(kind=FindingKind.MISSING, note="faltou Moabe", segment_id=over_monday.id, chunk=1)
    ]
    await save_back_translation(db_session, await get_session(db_session, session.id), state)

    release = await approve_release(
        db_session, await get_session(db_session, session.id), forced_by="a-facilitadora"
    )

    assert release.forced_open_findings == []
    assert release.packet["back_translation"]["findings"] == []
