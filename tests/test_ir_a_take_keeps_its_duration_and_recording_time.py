"""ENG-1273 — each take keeps its duration and its recording time.

A take recorded on the tablet keeps the tablet's own clock as its **Recording time**, however
late its upload lands; a joined or spliced **Part**, and a take sent with no time, keep the
server's. The tablet's fingerprint and length are checked against the bytes and refused when
they differ, never corrected. Every case sends real 16 kHz mono WAV through the room's doors and
reads what the tablet, the consultant and the **Packet** are served.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import wave
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSceneRehearsal, IRSession, IRTake
from app.db.models.project import Project
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.takes import takes_of
from tests.baker import grant_room_app_role, make_app, make_role, make_user
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    TABLET,
    at_the_desk,
    desk_retro,
    reported_playback,
)
from tests.room_harness import (
    nothing_is_read_ahead,
    rehearsed_in_parts,
    release_packet,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.scene_rehearsal_harness import recording
from tests.sentence_harness import re_record, spoken

TEN_OH_TWO = "2026-10-20T10:02:00+00:00"
WAV_FORMAT_OF_THE_TICKET = {
    "container": "wav",
    "codec": "pcm_s16le",
    "sample_rate": 16000,
    "channels": 1,
}


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
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.fixture()
async def consultant(db_session: AsyncSession) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
async def session(db_session: AsyncSession, client: httpx.AsyncClient) -> IRSession:
    rehearsing, _ = await rehearsed_in_parts(db_session, 0)
    return rehearsing


def sha(audio: bytes) -> str:
    return hashlib.sha256(audio).hexdigest()


def the_second_now() -> datetime:
    """Now, to the second: the server's clock may be the database's, which keeps no less."""
    return datetime.now(UTC).replace(microsecond=0)


def instant(served: str) -> datetime:
    return datetime.fromisoformat(served)


async def send(
    client: httpx.AsyncClient,
    session_id: str,
    audio: bytes,
    *,
    part: int = 1,
    content_type: str = "audio/wav",
    **fields: object,
) -> httpx.Response:
    """A part sent up the way the tablet sends it, with whichever of its values the case names."""
    data = {"kind": "ensaio", "scope": f"parte-{part}", "chunk_index": str(part)}
    data |= {name: str(value) for name, value in fields.items()}
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Device": TABLET},
        data=data,
        files={"file": ("gravacao.wav", audio, content_type)},
    )


async def kept(client: httpx.AsyncClient, session_id: str, audio: bytes, **fields: Any) -> dict:
    answer = await send(client, session_id, audio, **fields)
    assert answer.status_code == 200, answer.text
    return answer.json()


async def tablet_list(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    answer = await client.get(
        f"{PREFIX}/sessions/{session_id}/takes", headers={"X-Room-Device": TABLET}
    )
    assert answer.status_code == 200, answer.text
    return answer.json()["takes"]


async def consultant_read(
    client: httpx.AsyncClient, consultant: dict[str, str], session_id: str
) -> list[dict[str, Any]]:
    answer = await client.get(
        f"{PREFIX}/facilitator/sessions/{session_id}/mother-tongue-takes", headers=consultant
    )
    assert answer.status_code == 200, answer.text
    return answer.json()["takes"]


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


async def ready_to_release(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """Each part told back whole, the telling checked and played: the packet the Desk reads."""
    told = {stretch.take_id for stretch in await final_segments(db, session.id)}
    for index, take in enumerate(await takes_of(db, session.id), start=1):
        if take.kind.value == "ensaio" and take.id not in told:
            await capture_segment(
                db,
                session,
                take_id=take.id,
                starts_ms=0,
                ends_ms=1000,
                bridge_take_id=f"retro-{index}",
                transcript=f"parte {index} contada de volta",
            )
    stretches = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=session.pericope,
        findings=[],
        checked=True,
        analysed_segment_ids=[stretch.id for stretch in stretches],
    )
    await reported_playback(db, session, state)
    return await release_packet(db, session)


async def takes_holding(db: AsyncSession, audio: bytes) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(IRTake).where(IRTake.sha256 == sha(audio)))
        or 0
    )


async def test_a_part_recorded_at_10_02_and_uploaded_at_13_40_keeps_10_02_as_its_recording_time(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    audio = recording(3, 1)

    answer = await kept(
        client,
        session.id,
        audio,
        recorded_at="2026-10-20T10:02:00Z",
        duration_ms=3000,
        sha256=sha(audio),
    )

    assert answer["recorded_at"] == TEN_OH_TWO
    assert [take["recorded_at"] for take in await tablet_list(client, session.id)] == [TEN_OH_TWO]
    assert [
        take["recorded_at"] for take in await consultant_read(client, consultant, session.id)
    ] == [TEN_OH_TWO]
    packet = await ready_to_release(db_session, session)
    assert packet["audio"]["rehearsal_takes"][0]["recorded_at"] == TEN_OH_TWO


async def test_a_recording_time_sent_on_another_clock_is_kept_as_the_same_instant(
    client: httpx.AsyncClient, session: IRSession
) -> None:
    answer = await kept(
        client, session.id, recording(3, 2), recorded_at="2026-10-20T07:02:00-03:00"
    )

    assert answer["recorded_at"] == TEN_OH_TWO


async def test_the_retroverification_file_says_the_parts_recording_time_not_its_upload_time(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession
) -> None:
    room_app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(
        db_session, room_app.id, role_key="facilitator", label="Facilitator", is_system=True
    )
    team = await db_session.get(Project, session.project_id)
    assert team is not None
    desk, _user = await at_the_desk(db_session, room_app, team)
    await kept(client, session.id, recording(3, 3), recorded_at="2026-10-20T10:02:00Z")

    answer = await client.get(desk_retro(session.id), headers=desk)

    assert answer.status_code == 200, answer.text
    assert [take["recorded_at"] for take in answer.json()["takes"]] == [TEN_OH_TWO]


async def test_every_take_in_the_packet_carries_the_length_of_its_sound(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession
) -> None:
    await kept(client, session.id, recording(3, 4), part=1, duration_ms=3000)
    await kept(client, session.id, recording(2.5, 5), part=2)

    packet = await ready_to_release(db_session, session)

    assert [take["duration_ms"] for take in packet["audio"]["rehearsal_takes"]] == [3000, 2500]
    assert packet["schema_version"] == "tripod.internalization-release.v0.8"


async def test_a_take_sent_with_no_time_nor_length_keeps_the_servers_clock_and_its_measured_length(
    client: httpx.AsyncClient, session: IRSession
) -> None:
    before = the_second_now()
    answer = await kept(client, session.id, recording(2.5, 6))
    after = datetime.now(UTC)

    assert before <= instant(answer["recorded_at"]) <= after
    assert answer["duration_ms"] == 2500


async def test_a_joined_part_keeps_the_servers_clock_and_the_packet_carries_no_tablet_time(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession
) -> None:
    origin = await a_scene_rehearsal(db_session, session)
    before = the_second_now()
    tablet_time = (before - timedelta(minutes=1)).isoformat()
    answer = await kept(
        client, session.id, recording(3, 7), origin=origin.id, recorded_at=tablet_time
    )
    after = datetime.now(UTC)

    assert before <= instant(answer["recorded_at"]) <= after
    packet = await ready_to_release(db_session, session)
    (take,) = packet["audio"]["rehearsal_takes"]
    assert before <= instant(take["recorded_at"]) <= after
    assert tablet_time not in json.dumps(packet)
    assert tablet_time.replace("+00:00", "Z") not in json.dumps(packet)
    assert "device_clock_offset_ms" not in take


async def test_a_joined_part_from_a_tablet_8_minutes_behind_keeps_the_offset_for_the_observer_only(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    origin = await a_scene_rehearsal(db_session, session)
    behind = (datetime.now(UTC) - timedelta(minutes=8)).isoformat()

    answer = await kept(client, session.id, recording(3, 8), origin=origin.id, recorded_at=behind)

    (observed,) = await consultant_read(client, consultant, session.id)
    assert abs(observed["device_clock_offset_ms"] - -480_000) <= 5_000
    assert "device_clock_offset_ms" not in answer
    assert all(
        "device_clock_offset_ms" not in take for take in await tablet_list(client, session.id)
    )
    packet = await ready_to_release(db_session, session)
    assert "device_clock_offset_ms" not in json.dumps(packet)


async def test_a_joined_part_from_a_tablet_four_minutes_off_keeps_no_offset(
    client: httpx.AsyncClient,
    consultant: dict[str, str],
    session: IRSession,
    db_session: AsyncSession,
) -> None:
    origin = await a_scene_rehearsal(db_session, session)
    ahead = (datetime.now(UTC) + timedelta(minutes=4)).isoformat()

    await kept(client, session.id, recording(3, 9), origin=origin.id, recorded_at=ahead)

    (observed,) = await consultant_read(client, consultant, session.id)
    assert observed["device_clock_offset_ms"] is None


async def test_a_part_recorded_on_a_tablet_8_minutes_behind_keeps_the_tablets_time_and_no_offset(
    client: httpx.AsyncClient, consultant: dict[str, str], session: IRSession
) -> None:
    behind = the_second_now() - timedelta(minutes=8)

    answer = await kept(client, session.id, recording(3, 10), recorded_at=behind.isoformat())

    assert instant(answer["recorded_at"]) == behind
    (observed,) = await consultant_read(client, consultant, session.id)
    assert observed["device_clock_offset_ms"] is None


async def test_a_release_whose_every_part_is_16_khz_wav_states_the_wav_audio_format(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession
) -> None:
    await kept(client, session.id, recording(3, 11), part=1)
    await kept(client, session.id, recording(3, 12), part=2)

    packet = await ready_to_release(db_session, session)

    assert packet["audio_format"] == WAV_FORMAT_OF_THE_TICKET


class BucketWhereBothUploadsMeet(MemoryStore):
    """A bucket that holds every write until two have reached it, so both passed the first look."""

    def __init__(self) -> None:
        super().__init__()
        self.arrived = 0
        self.both = asyncio.Event()

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.arrived += 1
        if self.arrived == 2:
            self.both.set()
        await asyncio.wait_for(self.both.wait(), 10)
        await super().put(key, data, content_type)


async def test_the_same_bytes_sent_twice_at_once_under_audio_wav_and_audio_mp4_are_one_take(
    db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    bucket = BucketWhereBothUploadsMeet()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)
    audio = recording(3, 13)
    async with room_client(db_session, monkeypatch, per_request=rival_factory) as racing:
        rehearsing, _ = await rehearsed_in_parts(db_session, 0)

        first, second = await asyncio.gather(
            send(racing, rehearsing.id, audio, content_type="audio/wav"),
            send(racing, rehearsing.id, audio, content_type="audio/mp4"),
        )
        third = await send(racing, rehearsing.id, audio, content_type="audio/wav")

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert first.json()["take_id"] == second.json()["take_id"]
    assert await takes_holding(db_session, audio) == 1
    assert third.status_code == 200, third.text
    assert third.json()["take_id"] == first.json()["take_id"]


async def test_a_fingerprint_that_is_not_the_recordings_is_refused_and_nothing_is_kept(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession, store: MemoryStore
) -> None:
    audio = recording(3, 14)

    answer = await send(client, session.id, audio, sha256=sha(b"outros bytes"))

    assert answer.status_code == 422, answer.text
    assert answer.json()["code"] == "TAKE_FINGERPRINT_DIFFERS"
    assert await takes_of(db_session, session.id) == []
    assert store.objects == {}


async def test_a_length_that_is_not_the_recordings_is_refused_and_nothing_is_kept(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession, store: MemoryStore
) -> None:
    answer = await send(client, session.id, recording(3, 15), duration_ms=9000)

    assert answer.status_code == 422, answer.text
    assert answer.json()["code"] == "TAKE_DURATION_DIFFERS"
    assert await takes_of(db_session, session.id) == []
    assert store.objects == {}


async def test_a_length_within_a_tenth_of_a_second_of_the_sound_is_kept_as_the_tablet_sent_it(
    client: httpx.AsyncClient, session: IRSession
) -> None:
    await kept(client, session.id, recording(3, 16), duration_ms=3080)

    assert [take["duration_ms"] for take in await tablet_list(client, session.id)] == [3080]


async def test_a_recording_time_never_moves_when_the_take_is_sent_again(
    client: httpx.AsyncClient, session: IRSession
) -> None:
    audio = recording(3, 17)
    first = await kept(client, session.id, audio, recorded_at="2026-10-20T10:02:00Z")

    again = await kept(client, session.id, audio, recorded_at="2026-10-20T11:00:00Z")

    assert again["take_id"] == first["take_id"]
    assert again["recorded_at"] == TEN_OH_TWO


async def test_a_recording_time_with_no_offset_is_refused(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession
) -> None:
    answer = await send(client, session.id, recording(3, 18), recorded_at="2026-10-20T10:02:00")

    assert answer.status_code == 422, answer.text
    assert "code" not in answer.json()
    assert await takes_of(db_session, session.id) == []


async def test_a_told_back_stretchs_take_carries_the_length_of_its_sound(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession
) -> None:
    part = await kept(client, session.id, recording(3, 19))
    before = the_second_now()
    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={"take_id": part["take_id"], "starts_ms": "0", "ends_ms": "3000"},
        files={"file": ("trecho.wav", recording(1.5, 20), "audio/wav")},
    )
    after = datetime.now(UTC)
    assert told.status_code == 200, told.text

    packet = await ready_to_release(db_session, session)

    (retro,) = packet["back_translation"]["retro_takes"]
    assert retro["duration_ms"] == 1500
    assert before <= instant(retro["recorded_at"]) <= after


def wav_ms(audio: bytes) -> int:
    with wave.open(io.BytesIO(audio), "rb") as file:
        return round(file.getnframes() * 1000 / file.getframerate())


async def test_a_sentence_laid_into_a_part_makes_a_take_on_the_servers_clock_of_the_spliced_length(
    client: httpx.AsyncClient, session: IRSession, db_session: AsyncSession, store: MemoryStore
) -> None:
    part = await kept(client, session.id, recording(4, 21), recorded_at="2026-10-20T10:02:00Z")
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

    before = the_second_now()
    laid = await re_record(client, session.id, first.id, spoken(1.0))
    after = datetime.now(UTC)

    assert laid.status_code == 200, laid.text
    new_take_id = laid.json()["segments"][0]["take_id"]
    assert new_take_id != part["take_id"]
    (spliced,) = [
        take for take in await tablet_list(client, session.id) if take["take_id"] == new_take_id
    ]
    assert before <= instant(spliced["recorded_at"]) <= after
    row = await db_session.get(IRTake, new_take_id)
    assert row is not None
    assert spliced["duration_ms"] == wav_ms(store.objects[row.storage_key])
