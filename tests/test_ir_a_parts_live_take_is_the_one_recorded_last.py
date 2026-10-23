"""ENG-1760 — a part's live take is the one recorded last, so a reinstall never hides it.

A reinstalled tablet, or a second one, counts its passes from 1 again, so the pass the tablet
sends no longer says which recording of a part came last. The **Recording time** does: under one
part number the take recorded last is the part, the pass breaks a tie, and a take with no
Recording time of its own keeps the pass order and comes before every take that has one. Every
case sends real WAV through the room's doors and reads which take is the part where the Desk,
the tablet, the consultant and the **Packet** read it. Expected values come from the ticket and
Henok's decision of 2026-10-22.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.core.config import get_settings
from app.db.models.auth import App
from app.db.models.internalization_room import IRSceneRehearsal, IRSession, IRTake
from app.models.internalization_room import PlayedTake
from app.services.internalization_room import report_playback
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import capture_segment, final_segments
from tests.baker import grant_room_app_role, make_app, make_role, make_user
from tests.hard_stretch_harness import MemoryStore
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


async def told_back_whole(db: AsyncSession, session: IRSession, take_id: str) -> None:
    await capture_segment(
        db,
        session,
        take_id=take_id,
        starts_ms=0,
        ends_ms=1000,
        bridge_take_id="retro-1",
        transcript="a parte contada de volta",
    )


async def a_checked_telling(db: AsyncSession, session: IRSession) -> None:
    told = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=P, findings=[], checked=True, analysed_segment_ids=[stretch.id for stretch in told]
    )
    await reported_playback(db, session, state)


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


async def test_a_take_recorded_monday_that_reaches_the_server_after_tuesdays_is_never_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    tuesday = await recorded_again_on_tuesday_after_a_reinstall(client, credential, session)
    await recorded_on_monday(client, credential, session)

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id)
        == tuesday["take_id"]
    )
    assert the_tablets_part(await tablet_list(client, credential, session.id)) == tuesday["take_id"]


async def test_the_late_take_recorded_monday_retires_none_of_the_parts_stretches(
    client, db_session, team, session
):
    _project, credential = team
    tuesday = await recorded_again_on_tuesday_after_a_reinstall(client, credential, session)
    await told_back_whole(db_session, session, tuesday["take_id"])
    await a_checked_telling(db_session, session)

    await recorded_on_monday(client, credential, session)

    standing = await final_segments(db_session, session.id)
    assert [stretch.take_id for stretch in standing] == [tuesday["take_id"]]
    assert (await stored_telling_back(db_session, session)).checked is True


async def test_two_takes_with_the_same_recording_time_the_higher_pass_is_the_part(
    client, db_session, room_app, team, session
):
    project, credential = team
    second_pass = await send(
        client, credential, session.id, recording(2, 1), pass_number=2, recorded_at=TUESDAY
    )
    await send(client, credential, session.id, recording(2, 2), pass_number=1, recorded_at=TUESDAY)

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id)
        == second_pass["take_id"]
    )


async def test_takes_sent_with_no_recording_time_keep_the_pass_order(
    client, db_session, room_app, team, session
):
    project, credential = team
    second_pass = await send(client, credential, session.id, recording(2, 1), pass_number=2)
    await send(client, credential, session.id, recording(2, 2), pass_number=1)

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id)
        == second_pass["take_id"]
    )


async def test_a_take_with_a_recording_time_is_the_part_over_one_sent_with_none(
    client, db_session, room_app, team, session
):
    project, credential = team
    timed = await send(
        client, credential, session.id, recording(2, 1), pass_number=1, recorded_at=MONDAY
    )
    await send(client, credential, session.id, recording(2, 2), pass_number=2)

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id) == timed["take_id"]
    )


async def test_a_part_joined_from_a_scene_rehearsal_is_the_part_over_a_take_recorded_before_it(
    client, db_session, room_app, team, session
):
    project, credential = team
    await send(
        client, credential, session.id, recording(2, 1), pass_number=1, recorded_at=an_hour_ago()
    )
    origin = await a_scene_rehearsal(db_session, session)
    joined = await send(
        client, credential, session.id, recording(2, 2), pass_number=1, origin=origin.id
    )

    assert (
        await the_desks_part(client, db_session, room_app, project, session.id) == joined["take_id"]
    )


async def test_a_sentence_laid_into_a_part_timed_on_the_tablet_keeps_the_spliced_part_as_the_part(
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


async def test_a_part_sent_with_no_recording_time_and_spliced_is_still_replaced_by_its_next_pass(
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


async def test_a_take_stored_before_its_mark_was_written_still_reads_by_its_recording_time(
    client, db_session, team, session
):
    project, credential = team
    monday = ensaio_take(
        session.id,
        scope="parte-1",
        ordinal=1,
        pass_number=2,
        sha256="m" * 64,
        project_id=project.id,
    )
    tuesday = ensaio_take(
        session.id,
        scope="parte-1",
        ordinal=1,
        pass_number=1,
        sha256="t" * 64,
        project_id=project.id,
    )
    for take, recorded_at in ((monday, MONDAY), (tuesday, TUESDAY)):
        take.recorded_at = datetime.fromisoformat(recorded_at)
        take.recorded_at_known = False
        db_session.add(take)
    await db_session.commit()

    assert the_tablets_part(await tablet_list(client, credential, session.id)) == tuesday.id


async def test_a_take_that_became_the_part_when_the_order_changed_is_not_told_by_the_one_before(
    client, db_session, team, session
):
    _project, credential = team
    monday = await send(
        client, credential, session.id, recording(2, 1), tablet=OLD_TABLET, pass_number=2
    )
    tuesday = await send(
        client, credential, session.id, recording(2, 2), tablet=NEW_TABLET, pass_number=1
    )
    await told_back_whole(db_session, session, monday["take_id"])
    await a_checked_telling(db_session, session)
    for take_id, recorded_at in ((monday["take_id"], MONDAY), (tuesday["take_id"], TUESDAY)):
        await db_session.execute(
            update(IRTake)
            .where(IRTake.id == take_id)
            .values(recorded_at=datetime.fromisoformat(recorded_at))
        )
    await db_session.commit()
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
