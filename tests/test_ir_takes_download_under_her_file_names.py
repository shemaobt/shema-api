"""ENG-1283 — the takes of a session download under her file names through links that last an hour.

A facilitator hands Refine the rehearsal takes of a session, and a take that a later one replaced
is listed apart. Every case reads the list the Desk reads and then the link the way a browser's
download would: the object it names, how long it lasts, the name it saves under. Expected names
come from the ticket and from her ``export.ts`` and ``retroExport.ts``.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import uuid
import wave
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import back_translation as bt_api
from app.core.config import get_settings
from app.core.enums import ProjectRole
from app.db.models.auth import App
from app.db.models.internalization_room import IRRelease, IRSession, IRTake
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.archives import archive_pericope
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import final_segments
from tests.baker import (
    grant_room_app_role,
    make_app,
    make_language,
    make_project,
    make_project_user_access,
    make_role,
    make_user,
)
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    TABLET,
    P,
    a_claimed_device,
    at_the_desk,
    judged_packet,
    reported_playback,
    team_headers,
    team_release,
    the_one_part_of,
)
from tests.room_harness import (
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    tell_back_about,
    the_bucket_is_in_memory,
    upload_a_part,
)
from tests.scene_rehearsal_harness import recording, the_take_lasts_as_long_as_its_wav

BUCKET = "balde-de-teste"
RELEASE_V1 = "internalize-terena-p03-v1"
RELEASE_V2 = "internalize-terena-p03-v2"
AN_HOUR = 3600


@dataclass
class Link:
    """What a browser learns from a signed link before it downloads anything."""

    key: str
    lasts_s: int
    saves_as: str


def read_link(url: str) -> Link:
    parts = urlsplit(url)
    asked = parse_qs(parts.query)
    return Link(
        key=parts.path.removeprefix(f"/{BUCKET}/"),
        lasts_s=int(asked["X-Goog-Expires"][0]),
        saves_as=asked["response-content-disposition"][0],
    )


def saves_as(filename: str) -> str:
    return f'attachment; filename="{filename}"'


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    the_take_lasts_as_long_as_its_wav(monkeypatch)

    async def said(*_: Any, **__: Any) -> str:
        return "a equipe contou o trecho de volta"

    monkeypatch.setattr(bt_api, "heard", said)


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


def downloads_of(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/takes/downloads"


async def read_downloads(
    client: httpx.AsyncClient, desk: dict[str, str], session_id: str
) -> dict[str, Any]:
    answer = await client.get(downloads_of(session_id), headers=desk)
    assert answer.status_code == 200, answer.text
    return answer.json()


async def a_rehearsal(db: AsyncSession, project_id: str, *, language: str = "pt") -> IRSession:
    from app.services.internalization_room.sessions import create_session

    return await create_session(db, pericope=P, project_id=project_id, language=language)


async def send(
    client: httpx.AsyncClient,
    credential: str,
    session_id: str,
    audio: bytes,
    *,
    part: int | None = 1,
    content_type: str = "audio/wav",
) -> dict[str, Any]:
    answer = await upload_a_part(
        client,
        session_id,
        part=part,
        audio=audio,
        content_type=content_type,
        headers=team_headers(credential),
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


def the_second_now() -> datetime:
    return datetime.now(UTC)


async def a_beat() -> None:
    await asyncio.sleep(0.01)


async def ready_to_approve(
    db: AsyncSession, project_id: str, content_types: tuple[str, ...]
) -> IRSession:
    """A session rehearsed in one part per content type, told back and heard: ready to approve."""
    audio = tuple(recording(1, tone) for tone in range(1, len(content_types) + 1))
    session, _parts = await rehearsed_in_parts(
        db, len(content_types), project_id=project_id, content_types=content_types, audio=audio
    )
    await a_checked_telling(db, session)
    return session


async def a_checked_telling(db: AsyncSession, session: IRSession) -> None:
    told = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=P, findings=[], checked=True, analysed_segment_ids=[stretch.id for stretch in told]
    )
    await reported_playback(db, session, state)


async def approved(client: httpx.AsyncClient, credential: str, session: IRSession) -> None:
    answer = await client.post(team_release(session.id), headers=team_headers(credential))
    assert answer.status_code == 200, answer.text


async def test_three_live_parts_download_under_the_release_name_and_each_parts_key(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_to_approve(db_session, project.id, ("audio/wav",) * 3)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["release_id"] == RELEASE_V1
    names = [each["filename"] for each in listed["takes"]]
    assert names == [f"{RELEASE_V1}-S1.wav", f"{RELEASE_V1}-S2.wav", f"{RELEASE_V1}-S3.wav"]
    for each in listed["takes"]:
        assert read_link(each["url"]).saves_as == saves_as(each["filename"])


async def test_a_part_recorded_again_is_listed_apart_stamped_and_named_substituida_with_its_id(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    first = await send(client, credential, session.id, recording(2, 1))
    await a_beat()
    before = the_second_now()
    second = await send(client, credential, session.id, recording(2, 2))
    after = the_second_now()
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert [(each["key"], each["take_id"]) for each in listed["takes"]] == [
        ("S1", second["take_id"])
    ]
    [replaced] = listed["superseded_takes"]
    assert (replaced["key"], replaced["take_id"]) == ("S1", first["take_id"])
    assert replaced["filename"] == f"{RELEASE_V1}-S1-substituida-{first['take_id']}.wav"
    assert before <= datetime.fromisoformat(replaced["superseded_at"]) <= after


async def test_a_part_recorded_three_times_stamps_each_earlier_take_with_the_next_ones_arrival(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    first = await send(client, credential, session.id, recording(2, 1))
    await a_beat()
    second_from = the_second_now()
    second = await send(client, credential, session.id, recording(2, 2))
    second_to = the_second_now()
    await a_beat()
    third_from = the_second_now()
    third = await send(client, credential, session.id, recording(2, 3))
    third_to = the_second_now()
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert [each["take_id"] for each in listed["takes"]] == [third["take_id"]]
    replaced_first, replaced_second = listed["superseded_takes"]
    assert replaced_first["take_id"] == first["take_id"]
    assert replaced_second["take_id"] == second["take_id"]
    assert second_from <= datetime.fromisoformat(replaced_first["superseded_at"]) <= second_to
    assert third_from <= datetime.fromisoformat(replaced_second["superseded_at"]) <= third_to


async def test_a_take_replaced_before_the_stamp_existed_is_listed_apart_with_no_time(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    first = await send(client, credential, session.id, recording(2, 1))
    await send(client, credential, session.id, recording(2, 2))
    await db_session.execute(update(IRTake).values(superseded_at=None))
    await db_session.commit()
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    [replaced] = listed["superseded_takes"]
    assert replaced["take_id"] == first["take_id"]
    assert replaced["superseded_at"] is None


async def _stamps(db_session: AsyncSession, session_id: str) -> dict[str, datetime | None]:
    rows = await db_session.execute(
        select(IRTake.id, IRTake.superseded_at).where(IRTake.session_id == session_id)
    )
    return dict(rows.tuples().all())


async def test_an_upload_stamps_the_part_it_displaces_with_the_arrival_and_nothing_else(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    first = await send(client, credential, session.id, recording(2, 1))
    before = the_second_now()
    second = await send(client, credential, session.id, recording(2, 2))
    after = the_second_now()

    stamps = await _stamps(db_session, session.id)

    assert before <= stamps[first["take_id"]] <= after
    assert stamps[second["take_id"]] is None


async def test_a_whole_is_stamped_by_the_first_scene_part_and_the_scene_part_is_not(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    whole = await send(client, credential, session.id, recording(2, 1), part=None)
    scene = await send(client, credential, session.id, recording(2, 2), part=1)

    stamps = await _stamps(db_session, session.id)

    assert stamps[whole["take_id"]] is not None
    assert stamps[scene["take_id"]] is None


async def test_an_upload_gives_no_time_to_a_take_replaced_before_the_stamp_existed(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    first = await send(client, credential, session.id, recording(2, 1))
    second = await send(client, credential, session.id, recording(2, 2))
    await db_session.execute(update(IRTake).values(superseded_at=None))
    await db_session.commit()
    third = await send(client, credential, session.id, recording(2, 3))

    stamps = await _stamps(db_session, session.id)

    assert stamps[first["take_id"]] is None
    assert stamps[second["take_id"]] is not None
    assert stamps[third["take_id"]] is None


async def test_a_whole_that_arrives_over_scene_parts_is_stamped_itself_and_displaces_none(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    scene = await send(client, credential, session.id, recording(2, 1), part=1)
    whole = await send(client, credential, session.id, recording(2, 2), part=None)

    stamps = await _stamps(db_session, session.id)

    assert stamps[whole["take_id"]] is not None
    assert stamps[scene["take_id"]] is None


async def test_every_link_lasts_an_hour_and_the_list_says_so(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(2, 1))
    await send(client, credential, session.id, recording(2, 2))
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    links = [*listed["takes"], *listed["superseded_takes"]]
    assert len(links) == 2
    assert {read_link(each["url"]).lasts_s for each in links} == {AN_HOUR}
    assert listed["links_valid_for_s"] == AN_HOUR


async def test_the_file_behind_a_link_is_the_one_the_fingerprint_names(
    client, db_session, room_app, store
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    replaced_audio = recording(2, 1)
    live_audio = recording(2, 2)
    await send(client, credential, session.id, replaced_audio)
    await send(client, credential, session.id, live_audio)
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    [live] = listed["takes"]
    [replaced] = listed["superseded_takes"]
    for entry, sent in ((live, live_audio), (replaced, replaced_audio)):
        behind_the_link = store.objects[read_link(entry["url"]).key]
        assert hashlib.sha256(behind_the_link).hexdigest() == entry["sha256"]
        assert entry["sha256"] == hashlib.sha256(sent).hexdigest()


async def test_each_take_in_the_list_carries_its_key_length_size_and_fingerprint(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    audio = recording(1.5, 1)
    sent = await send(client, credential, session.id, audio)
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    [entry] = listed["takes"]
    assert entry["take_id"] == sent["take_id"]
    assert entry["key"] == "S1"
    assert entry["duration_ms"] == 1500
    assert entry["size_bytes"] == len(audio)
    assert entry["sha256"] == hashlib.sha256(audio).hexdigest()
    assert len(entry["sha256"]) == 64
    assert entry["content_type"] == "audio/wav"


async def test_a_superseded_take_carries_its_own_length_not_the_parts(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(2, 1))
    await send(client, credential, session.id, recording(3, 2))
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert [each["duration_ms"] for each in listed["superseded_takes"]] == [2000]
    assert [each["duration_ms"] for each in listed["takes"]] == [3000]


async def test_the_name_follows_the_passages_latest_release(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_to_approve(db_session, project.id, ("audio/wav",))
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)
    first_read = await read_downloads(client, desk, session.id)
    assert first_read["release_id"] == RELEASE_V1

    again = await record_the_part_again(
        db_session,
        session,
        await the_one_part_of(db_session, session),
        sha256=hashlib.sha256(recording(1, 9)).hexdigest(),
    )
    await tell_back_about(db_session, session, again, bridge_take_id="retro-novo")
    await a_checked_telling(db_session, session)
    await approved(client, credential, session)

    listed = await read_downloads(client, desk, session.id)

    assert listed["release_id"] == RELEASE_V2
    every_name = [each["filename"] for each in (*listed["takes"], *listed["superseded_takes"])]
    assert len(every_name) == 2
    assert all(name.startswith(f"{RELEASE_V2}-S1") for name in every_name)


async def test_a_draft_re_opened_after_its_approval_names_its_files_by_the_next_version(
    client, db_session, room_app
):
    """ENG-1260: a file names a release only while the draft stands under it (ADR 0081)."""
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_to_approve(db_session, project.id, ("audio/wav",))
    await approved(client, credential, session)
    await record_the_part_again(
        db_session,
        session,
        await the_one_part_of(db_session, session),
        sha256=hashlib.sha256(recording(1, 9)).hexdigest(),
    )
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["release_id"] == RELEASE_V2
    assert [each["filename"].startswith(f"{RELEASE_V2}-S1") for each in listed["takes"]] == [True]


async def test_the_session_after_a_zerar_names_its_files_by_the_next_version_not_the_archived_one(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    zeroed = await ready_to_approve(db_session, project.id, ("audio/wav",))
    await approved(client, credential, zeroed)
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    await archive_pericope(db_session, facilitator, project_id=project.id, pericope=P)
    again, _parts = await rehearsed_in_parts(
        db_session, 1, project_id=project.id, content_types=("audio/wav",)
    )

    listed = await read_downloads(client, desk, again.id)

    assert listed["release_id"] == RELEASE_V2


async def test_a_session_a_zerar_archived_names_its_files_by_the_release_its_takes_were_approved_as(
    client, db_session, room_app
):
    """The next version's name is a live draft's; the archived one keeps its own."""
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    zeroed = await ready_to_approve(db_session, project.id, ("audio/wav",))
    await approved(client, credential, zeroed)
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    await archive_pericope(db_session, facilitator, project_id=project.id, pericope=P)

    listed = await read_downloads(client, desk, zeroed.id)

    assert listed["release_id"] == RELEASE_V1


async def test_sibling_sessions_re_opened_or_never_approved_are_named_apart_by_their_language(
    client, db_session, room_app
):
    """ENG-1782: one Zerar stamps every language of the passage with one archive, and a file name
    names one recording: the stamp is the archive's, UTC, and the session language tells siblings
    apart."""
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    reopened = await ready_to_approve(db_session, project.id, ("audio/wav",))
    await approved(client, credential, reopened)
    await record_the_part_again(
        db_session,
        reopened,
        await the_one_part_of(db_session, reopened),
        sha256=hashlib.sha256(recording(1, 9)).hexdigest(),
    )
    never_approved, _parts = await rehearsed_in_parts(
        db_session, 1, project_id=project.id, language="en", content_types=("audio/wav",)
    )
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    archive = await archive_pericope(db_session, facilitator, project_id=project.id, pericope=P)
    archive.archived_at = datetime(2026, 10, 24, 18, 30, tzinfo=UTC)
    await db_session.commit()
    zerada = "internalize-terena-p03-zerada-20261024-1830"

    first = await read_downloads(client, desk, reopened.id)
    second = await read_downloads(client, desk, never_approved.id)

    assert [each["filename"] for each in first["takes"]] == [f"{zerada}-pt-S1.m4a"]
    assert [each["filename"] for each in second["takes"]] == [f"{zerada}-en-S1.wav"]


async def test_the_session_approved_after_a_zerar_mints_a_version_no_zerada_file_carries(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    zeroed = await ready_to_approve(db_session, project.id, ("audio/wav",))
    await approved(client, credential, zeroed)
    await record_the_part_again(
        db_session,
        zeroed,
        await the_one_part_of(db_session, zeroed),
        sha256=hashlib.sha256(recording(1, 9)).hexdigest(),
    )
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    archive = await archive_pericope(db_session, facilitator, project_id=project.id, pericope=P)
    archive.archived_at = datetime(2026, 10, 24, 18, 30, tzinfo=UTC)
    await db_session.commit()
    archived = await read_downloads(client, desk, zeroed.id)
    again = await ready_to_approve(db_session, project.id, ("audio/wav",))
    await approved(client, credential, again)

    minted = await read_downloads(client, desk, again.id)

    zerada = "internalize-terena-p03-zerada-20261024-1830-pt"
    assert [each["filename"] for each in archived["takes"]] == [f"{zerada}-S1.m4a"]
    assert minted["release_id"] == RELEASE_V2
    assert [each["filename"] for each in minted["takes"]] == [f"{RELEASE_V2}-S1.wav"]


async def test_a_release_stored_before_adr_0048_names_the_files_by_its_uuid(
    client, db_session, room_app
):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_to_approve(db_session, project.id, ("audio/wav",))
    packet = await judged_packet(db_session, session)
    legacy_id = str(uuid.uuid4())
    packet["release_id"] = legacy_id
    packet["version"] = 1
    db_session.add(
        IRRelease(
            id=legacy_id,
            session_id=session.id,
            project_id=project.id,
            pericope=P,
            version=1,
            package_sha256=packet["package_sha256"],
            packet=packet,
            device_id=TABLET,
        )
    )
    await db_session.commit()
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["release_id"] == legacy_id
    assert [each["filename"] for each in listed["takes"]] == [f"{legacy_id}-S1.wav"]


async def test_before_any_release_the_files_carry_the_name_version_1_will_have(
    client, db_session, room_app
):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(
        db_session, 1, project_id=project.id, content_types=("audio/wav",)
    )
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["release_id"] == RELEASE_V1
    assert [each["filename"] for each in listed["takes"]] == [f"{RELEASE_V1}-S1.wav"]


async def test_a_rehearsal_told_whole_downloads_as_whole(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(2, 1), part=None)
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert [(each["key"], each["filename"]) for each in listed["takes"]] == [
        ("whole", f"{RELEASE_V1}-whole.wav")
    ]


async def test_a_whole_that_stepped_aside_for_a_scene_part_is_listed_as_superseded_under_whole(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    whole = await send(client, credential, session.id, recording(2, 1), part=None)
    await a_beat()
    before = the_second_now()
    scene = await send(client, credential, session.id, recording(2, 2), part=1)
    after = the_second_now()
    await a_beat()
    await send(client, credential, session.id, recording(2, 3), part=2)
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["takes"][0]["take_id"] == scene["take_id"]
    [stepped_aside] = listed["superseded_takes"]
    assert (stepped_aside["key"], stepped_aside["take_id"]) == ("whole", whole["take_id"])
    assert stepped_aside["filename"] == f"{RELEASE_V1}-whole-substituida-{whole['take_id']}.wav"
    assert before <= datetime.fromisoformat(stepped_aside["superseded_at"]) <= after


async def test_a_compressed_take_keeps_its_m4a(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, b"a equipe gravou a cena", content_type="audio/mp4")
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert [each["filename"] for each in listed["takes"]] == [f"{RELEASE_V1}-S1.m4a"]


async def test_a_telling_backs_take_is_not_a_download(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    rehearsed = await send(client, credential, session.id, recording(2, 1))
    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers=team_headers(credential),
        data={"take_id": rehearsed["take_id"], "starts_ms": "0", "ends_ms": "1000"},
        files={"file": ("trecho.m4a", b"a equipe contou de volta", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    desk, _user = await at_the_desk(db_session, room_app, project)
    everything = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/takes", headers=desk)
    telling_backs = [
        each["take_id"] for each in everything.json()["takes"] if each["kind"] == "retro"
    ]
    assert telling_backs

    listed = await read_downloads(client, desk, session.id)

    listed_ids = [each["take_id"] for each in (*listed["takes"], *listed["superseded_takes"])]
    assert listed_ids == [rehearsed["take_id"]]


async def test_a_part_the_text_seam_declared_has_no_file_to_download(client, db_session, room_app):
    from app.services.internalization_room.takes import declare_rehearsal_parts

    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await declare_rehearsal_parts(db_session, session, ["S1", "S2"])
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["takes"] == []
    assert listed["superseded_takes"] == []


async def test_a_tablets_credential_does_not_open_the_downloads(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(2, 1))

    answer = await client.get(downloads_of(session.id), headers=team_headers(credential))

    assert answer.status_code == 401


async def test_a_signed_in_person_without_the_rooms_role_is_refused(client, db_session, room_app):
    from app.services.auth.issue_tokens import issue_tokens

    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(2, 1))
    stranger = await make_user(db_session, email="so-projeto@example.com")
    await make_project_user_access(
        db_session, project.id, stranger.id, role=ProjectRole.FACILITATOR
    )
    access, _refresh = await issue_tokens(db_session, stranger)

    answer = await client.get(
        downloads_of(session.id), headers={"Authorization": f"Bearer {access}"}
    )

    assert answer.status_code == 403


async def test_a_facilitator_of_another_team_reads_nothing_of_this_session(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(2, 1))
    other = await make_project(
        db_session, (await make_language(db_session, name="Guarani", code="gua")).id, name="Outro"
    )
    elsewhere, _user = await at_the_desk(db_session, room_app, other)
    owner, _owner = await at_the_desk(db_session, room_app, project)
    assert (await client.get(downloads_of(session.id), headers=owner)).status_code == 200

    foreign = await client.get(downloads_of(session.id), headers=elsewhere)
    nobody = str(uuid.uuid4())
    absent = await client.get(downloads_of(nobody), headers=elsewhere)

    assert foreign.status_code == absent.status_code == 404
    assert foreign.json()["detail"].replace(session.id, "ID") == (
        absent.json()["detail"].replace(nobody, "ID")
    )


async def test_a_consultant_reads_the_downloads_of_any_team(client, db_session, room_app):
    from app.services.auth.issue_tokens import issue_tokens

    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(2, 1))
    consultant = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, consultant.id, "consultant")
    access, _refresh = await issue_tokens(db_session, consultant)

    listed = await read_downloads(client, {"Authorization": f"Bearer {access}"}, session.id)

    assert [each["filename"] for each in listed["takes"]] == [f"{RELEASE_V1}-S1.wav"]


def whole_of(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/takes/whole"


async def three_scenes(client, db_session, credential, project_id) -> IRSession:
    session = await a_rehearsal(db_session, project_id)
    for part, seconds in enumerate((1, 2, 0.5), start=1):
        await send(client, credential, session.id, recording(seconds, part), part=part)
    return session


async def test_the_list_offers_the_whole_passage_with_the_sum_of_the_takes_lengths(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await three_scenes(client, db_session, credential, project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["whole"] == {
        "filename": f"{RELEASE_V1}-inteira.wav",
        "url": whole_of(session.id),
        "duration_ms": 3500,
    }


async def test_one_take_that_is_not_wav_takes_the_whole_out_of_the_list(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(1, 1), part=1)
    await send(client, credential, session.id, b"m4a bytes", part=2, content_type="audio/mp4")
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["whole"] is None


async def test_the_whole_answers_an_hour_link_as_json_of_the_three_takes_laid_end_to_end(
    client, db_session, room_app, store
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await three_scenes(client, db_session, credential, project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    answer = await client.get(whole_of(session.id), headers=desk, follow_redirects=False)

    assert answer.status_code == 200
    assert "location" not in answer.headers
    body = answer.json()
    assert set(body) == {"url", "expires_at"}
    remaining = datetime.fromisoformat(body["expires_at"]) - datetime.now(UTC)
    assert abs(remaining - timedelta(seconds=AN_HOUR)) < timedelta(seconds=30)
    link = read_link(body["url"])
    assert link.lasts_s == AN_HOUR
    assert link.saves_as == saves_as(f"{RELEASE_V1}-inteira.wav")
    assert pcm_of(store.objects[link.key]) == b"".join(
        pcm_of(recording(seconds, part)) for part, seconds in enumerate((1, 2, 0.5), start=1)
    )


async def test_the_whole_asked_twice_is_one_file_and_a_scene_recorded_again_makes_another(
    client, db_session, room_app, store
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await three_scenes(client, db_session, credential, project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    async def asked() -> str:
        answer = await client.get(whole_of(session.id), headers=desk, follow_redirects=False)
        return read_link(answer.json()["url"]).key

    first = await asked()
    stored = dict(store.objects)
    assert await asked() == first
    assert store.objects == stored, "o arquivo foi refeito"
    await send(client, credential, session.id, recording(2, 9), part=2)

    again = await asked()

    assert again != first
    assert first in store.objects, "o arquivo antigo foi apagado"
    assert pcm_of(store.objects[again]) == b"".join(
        pcm_of(recording(seconds, tone)) for seconds, tone in ((1, 1), (2, 9), (0.5, 3))
    ), "a gravação inteira levou uma tomada substituída"


async def test_a_take_the_record_calls_wav_but_whose_header_is_not_16khz_mono_refuses_the_whole(
    client, db_session, room_app, store
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await send(client, credential, session.id, recording(1, 1), part=1)
    await send(client, credential, session.id, a_wav(rate=44_100), part=2)
    desk, _user = await at_the_desk(db_session, room_app, project)

    answer = await client.get(whole_of(session.id), headers=desk, follow_redirects=False)

    assert answer.status_code == 409
    assert answer.json()["code"] == "NOT_ALL_WAV"
    assert not [key for key in store.objects if "/whole/" in key]


async def test_a_passage_with_no_take_offers_no_whole_in_the_list(client, db_session, room_app):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["whole"] is None


async def test_a_declared_part_that_says_wav_still_keeps_the_whole_out_of_the_list(
    client, db_session, room_app
):
    from app.services.internalization_room.takes import declare_rehearsal_parts

    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    await declare_rehearsal_parts(db_session, session, ["S1"], content_types={"S1": "audio/wav"})
    desk, _user = await at_the_desk(db_session, room_app, project)

    listed = await read_downloads(client, desk, session.id)

    assert listed["whole"] is None


async def test_a_passage_with_no_take_has_no_whole_to_build(client, db_session, room_app, store):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_rehearsal(db_session, project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    answer = await client.get(whole_of(session.id), headers=desk, follow_redirects=False)

    assert answer.status_code == 409
    assert answer.json()["code"] == "NOT_ALL_WAV"
    assert not [key for key in store.objects if "/whole/" in key]


async def test_a_tablets_credential_does_not_open_the_whole(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await three_scenes(client, db_session, credential, project.id)

    answer = await client.get(whole_of(session.id), headers=team_headers(credential))

    assert answer.status_code == 401


def pcm_of(audio: bytes) -> bytes:
    with wave.open(io.BytesIO(audio)) as file:
        return file.readframes(file.getnframes())


def a_wav(*, rate: int) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(b"\x07\x00" * rate)
    return out.getvalue()
