"""ENG-1274 — the Refine manifest has exactly her fields and carries no frase words.

Refine receives an approved passage through a **Manifest**: Marcia's document field for field
and in her order, named after the release, and served by the Desk's release read only for a
draft approved as it stands. It never carries a frase's words, a note, a superseded take, who
forced it, an order clock or a clock offset; the **Packet** stays the stored record.

Expected values come from the ticket, the Definer's Definition of 2026-10-22 and her
``src/draft/export.ts`` (Tripod-Internalization 18fa7c4), never from the code under test.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.core.config import get_settings
from app.db.models.auth import App
from app.db.models.internalization_room import IRRelease, IRSceneRehearsal, IRSession
from app.db.models.project import Project
from app.services.internalization_room import manifest as manifest_service
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.approved_draft import standing_approvals
from app.services.internalization_room.archives import archive_pericope
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
    Nuance,
    SupersededAttempt,
)
from app.services.internalization_room.canon import kept
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import create_session, get_session
from app.services.internalization_room.takes import current_parts, takes_of
from tests.baker import make_app, make_role
from tests.canon_harness import the_canon_moves_on
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    PREFIX,
    TABLET,
    P,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    at_the_desk,
    checked_telling_back,
    desk_release,
    desk_release_at,
    desk_retro,
    judged_packet,
    one_stretch,
    rehearsed_session,
    releases_of,
    reported_playback,
    team_headers,
    team_release,
    told_back_with_an_open_finding,
)
from tests.room_harness import (
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    tell_back_about,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
    upload_a_part,
)
from tests.scene_rehearsal_harness import recording
from tests.sentence_harness import PART, laid_in_and_told_again, rehearsed_in_wav
from tests.turn_harness import the_room_agent_is

BUCKET = "balde-de-teste"
AN_HOUR = 3600
P01 = "P01"
RUTH_P01_V1 = "internalize-terena-p01-v1"
NEW_PIN = "f" * 40
P01_MAP_SHA256 = "1852ecb9d42fb2bc084cabd79c09e26ada70d4f4189fc4aa0e584a50c15c8c05"
KEPT_P01_MAP_SHA256 = "0" * 64

HER_KEYS = [
    "releaseId",
    "pericopeId",
    "reference",
    "language",
    "sessionLanguage",
    "meaningMap",
    "grain",
    "clips",
    "finalizedAt",
    "finalizeCount",
    "sessionIds",
    "audioFormat",
    "integrity",
    "externalCheck",
    "check",
    "exportedAt",
]
HER_CHECK_KEYS = [
    "version",
    "status",
    "conferida",
    "forced",
    "heardComplete",
    "lastCheckAt",
    "findings",
    "retroUrl",
]
HER_CLIP_KEYS = [
    "key",
    "takeId",
    "sha256",
    "durationMs",
    "bytes",
    "contentType",
    "recordedAt",
    "filename",
    "url",
]
WAV_FORMAT = {"container": "wav", "codec": "pcm_s16le", "sampleRate": 16000, "channels": 1}

TOLD_WORDS = "PALAVRA-DA-FRASE-7c1"
OLD_WORDS = "PALAVRA-ANTIGA-DA-FRASE-7c1"
FINDING_NOTE = "NOTA-DO-ACHADO-7c1"
NUANCE_NOTE = "NOTA-DA-NUANCE-7c1"
NUANCE_QUOTE = "CITACAO-DA-NUANCE-7c1"
NUANCE_STORY = "HISTORIA-DA-NUANCE-7c1"
ATTEMPT_NOTE = "NOTA-DA-TENTATIVA-7c1"
PLANTED = [
    TOLD_WORDS,
    OLD_WORDS,
    FINDING_NOTE,
    NUANCE_NOTE,
    NUANCE_QUOTE,
    NUANCE_STORY,
    ATTEMPT_NOTE,
]
CONSULTANT_KEYS = {
    "text",
    "transcript",
    "note",
    "quote",
    "story",
    "superseded_segments",
    "divided_segments",
    "superseded_attempts",
    "retro_takes",
    "raised_questions",
    "open_questions",
    "played_by_take",
    "comprehension",
}
ON_FRASE_2 = {
    "kind": "nuance",
    "note": "O jeito de contar mudou.",
    "frase": 2,
    "quote": "contada de volta",
    "story": "a história conta de outro jeito",
}


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


class Speaker:
    def __init__(self) -> None:
        self.line = "Vocês contaram bem."

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.line


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    nothing_is_read_ahead(monkeypatch)

    async def said(*_: Any, **__: Any) -> str:
        return TOLD_WORDS

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
def analyst(monkeypatch: pytest.MonkeyPatch):
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    the_room_speaks(monkeypatch)
    voice = Speaker()
    the_room_agent_is(monkeypatch, turn=voice)
    return voice


async def ready_p01(db: AsyncSession, project_id: str, *, language: str = "pt") -> IRSession:
    """Ruth 1:1-5 told whole in one m4a part, told back clean and heard: ready to approve."""
    session, _take = await rehearsed_session(
        db, pericope=P01, project_id=project_id, language=language
    )
    await reported_playback(db, session, await checked_telling_back(db, session))
    return session


async def a_checked_telling(db: AsyncSession, session: IRSession) -> None:
    told = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=session.pericope,
        findings=[],
        checked=True,
        analysed_segment_ids=[stretch.id for stretch in told],
    )
    await reported_playback(db, session, state)


async def approved(
    client: httpx.AsyncClient, credential: str, session: IRSession
) -> dict[str, Any]:
    answer = await client.post(team_release(session.id), headers=team_headers(credential))
    assert answer.status_code == 200, answer.text
    assert answer.json()["blockers"] == [], answer.text
    return answer.json()


async def forced(client: httpx.AsyncClient, desk: dict[str, str], session: IRSession) -> None:
    answer = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert answer.status_code == 200, answer.text


async def manifest_of(
    client: httpx.AsyncClient, desk: dict[str, str], session: IRSession
) -> dict[str, Any]:
    read = await client.get(desk_release(session.id), headers=desk)
    assert read.status_code == 200, read.text
    return read.json()


async def p01_in_two_wav_parts(
    client: httpx.AsyncClient, db: AsyncSession, project_id: str, credential: str
) -> tuple[IRSession, list[bytes]]:
    """Ruth 1:1-5 in two WAV parts of 3 s and 2 s sent through the keep door, told and heard."""
    session = await create_session(db, pericope=P01, project_id=project_id, language="pt")
    sent = [recording(3, 1), recording(2, 2)]
    for part, audio in enumerate(sent, start=1):
        answer = await upload_a_part(
            client,
            session.id,
            part=part,
            audio=audio,
            content_type="audio/wav",
            headers=team_headers(credential),
        )
        assert answer.status_code == 200, answer.text
    session = await get_session(db, session.id)
    for index, take in enumerate(current_parts(await takes_of(db, session.id))):
        await capture_segment(
            db,
            session,
            take_id=take.id,
            starts_ms=0,
            ends_ms=take.duration_ms or CLIP_MS,
            bridge_take_id=f"retro-{index}",
            transcript=f"parte {index} contada de volta",
        )
    await a_checked_telling(db, session)
    return session, sent


def every_key(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from every_key(value)
    elif isinstance(node, list):
        for value in node:
            yield from every_key(value)


async def planted_and_forced(
    client: httpx.AsyncClient, db: AsyncSession, room_app: App
) -> tuple[IRSession, dict[str, str]]:
    """A P01 session carrying a planted word in every place a frase, a note or a quote can sit.

    Its one stretch was told, then told again (the old words are a superseded row), the analyst
    left a finding and a nuance on it, and an earlier attempt kept its own finding. The Desk
    forced it.
    """
    project, credential = await a_claimed_device(db, language_name="Terena")
    session, part = await rehearsed_session(db, pericope=P01, project_id=project.id)
    first = await one_stretch(db, session, text=OLD_WORDS)
    again = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{first.id}/replace",
        headers=team_headers(credential),
        data={"take_id": part.id, "starts_ms": "0", "ends_ms": str(CLIP_MS)},
        files={"file": ("trecho.m4a", b"a equipe contou de novo", "audio/mp4")},
    )
    assert again.status_code == 200, again.text
    [told] = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=P01,
        findings=[
            Finding(kind=FindingKind.ADDITION, note=FINDING_NOTE, segment_id=told.id, chunk=1)
        ],
        nuances=[
            Nuance(
                note=NUANCE_NOTE,
                chunk=1,
                segment_id=told.id,
                quote=NUANCE_QUOTE,
                story=NUANCE_STORY,
                take_id=told.take_id,
                starts_ms=told.starts_ms,
                ends_ms=told.ends_ms,
            )
        ],
        superseded=[
            SupersededAttempt(
                findings=[
                    Finding(
                        kind=FindingKind.ADDITION, note=ATTEMPT_NOTE, segment_id=first.id, chunk=1
                    )
                ]
            )
        ],
        checked=False,
        analysed_segment_ids=[told.id],
    )
    await reported_playback(db, session, state)
    desk, _user = await at_the_desk(db, room_app, project)
    await forced(client, desk, session)
    return session, desk


async def test_the_manifest_of_an_approved_ruth_p01_has_exactly_her_fields_in_her_order(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id, language="pt")
    approval = await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert list(manifest) == HER_KEYS
    assert manifest["releaseId"] == RUTH_P01_V1
    assert manifest["pericopeId"] == "P01"
    assert manifest["reference"] == "Ruth 1:1\u20135"
    assert manifest["language"] == "Terena"
    assert manifest["sessionLanguage"] == "pt"
    assert manifest["finalizeCount"] == 1
    assert manifest["finalizedAt"] == approval["approved_at"]
    assert manifest["externalCheck"] is None
    assert datetime.fromisoformat(manifest["exportedAt"]).tzinfo is not None


async def test_the_meaning_map_names_the_pin_it_was_read_at_after_the_canon_moves_on(
    client, db_session, room_app, monkeypatch, tmp_path: Path
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    served = kept.deployed_pin()

    def the_kept_p01_map_was_another_file(tree: Path) -> None:
        record = tree / "vendor" / "VENDOR_MANIFEST.json"
        manifest = json.loads(record.read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            if entry["path"] == "meaning-map/P01-Ruth-1-1-5.md":
                entry["sha256"] = KEPT_P01_MAP_SHA256
        record.write_text(json.dumps(manifest), encoding="utf-8")

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=the_kept_p01_map_was_another_file)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert manifest["meaningMap"] == {
        "id": "P01-Ruth-1-1-5",
        "file": "meaning-map/P01-Ruth-1-1-5.md",
        "pin": served,
        "sha256": KEPT_P01_MAP_SHA256,
    }
    assert manifest["meaningMap"]["pin"] != NEW_PIN


async def test_the_meaning_map_of_an_unmoved_canon_names_the_deployed_pin_and_her_file(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert manifest["meaningMap"] == {
        "id": "P01-Ruth-1-1-5",
        "file": "meaning-map/P01-Ruth-1-1-5.md",
        "pin": kept.deployed_pin(),
        "sha256": P01_MAP_SHA256,
    }


async def test_every_clip_has_her_keys_its_file_name_and_an_hour_link(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, sent = await p01_in_two_wav_parts(client, db_session, project.id, credential)
    await approved(client, credential, session)
    parts = current_parts(await takes_of(db_session, session.id))
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    clips = manifest["clips"]
    assert [clip["key"] for clip in clips] == ["S1", "S2"]
    for clip, part, audio, length_ms in zip(clips, parts, sent, (3000, 2000), strict=True):
        assert list(clip) == HER_CLIP_KEYS
        assert clip["takeId"] == part.id
        assert clip["durationMs"] == length_ms
        assert clip["filename"] == f"{RUTH_P01_V1}-{clip['key']}.wav"
        assert clip["sha256"] == hashlib.sha256(audio).hexdigest()
        assert clip["bytes"] == len(audio)
        assert clip["contentType"] == "audio/wav"
        link = read_link(clip["url"])
        assert link.lasts_s == AN_HOUR
        assert link.saves_as == saves_as(clip["filename"])
        assert link.key == part.storage_key
    assert manifest["grain"] == "scene"
    assert manifest["audioFormat"] == WAV_FORMAT


async def test_a_passage_told_whole_is_the_grain_whole_and_an_m4a_states_no_audio_format(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert manifest["grain"] == "whole"
    [clip] = manifest["clips"]
    assert clip["key"] == "whole"
    assert clip["filename"] == f"{RUTH_P01_V1}-whole.m4a"
    assert manifest["audioFormat"] is None


async def test_a_joined_part_carries_her_origin_and_never_the_clock_offset(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, parts = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    rehearsed_at = datetime(2026, 9, 1, 11, 30, tzinfo=UTC)
    rehearsal = IRSceneRehearsal(
        session_id=session.id,
        project_id=project.id,
        pericope=P,
        n=1,
        device_id=TABLET,
        storage_key=f"scene-rehearsals/{session.id}/1",
        size_bytes=2048,
        sha256="c" * 64,
        crc32c="AAAAAAA=",
        content_type="audio/wav",
        recorded_at=rehearsed_at,
    )
    db_session.add(rehearsal)
    await db_session.commit()
    joined = parts[0]
    joined.origin = rehearsal.id
    joined.device_clock_offset_ms = 360000
    await db_session.commit()
    joined_at = joined.created_at
    await a_checked_telling(db_session, session)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    first, second = manifest["clips"]
    assert first["origin"] == {
        "kind": "scene-rehearsal",
        "sessionId": session.id,
        "n": 1,
        "takeRecordedAt": rehearsed_at.isoformat(),
        "joinedAt": joined_at.astimezone(UTC).isoformat(),
    }
    assert list(first["origin"]) == ["kind", "sessionId", "n", "takeRecordedAt", "joinedAt"]
    assert "origin" not in second
    carried = json.dumps(manifest)
    for clock in ("360000", "device_clock_offset_ms", "clientClockSkewMs"):
        assert clock not in carried


async def test_a_joined_part_with_a_sentence_laid_in_keeps_the_time_it_was_joined(
    client, db_session, room_app, store
):
    session, (joined, _second), (part_1, _part_2) = await rehearsed_in_wav(
        db_session, store, [PART, PART]
    )
    rehearsal = IRSceneRehearsal(
        session_id=session.id,
        project_id=TABLET_TEAM,
        pericope=P,
        n=1,
        device_id=TABLET,
        storage_key=f"scene-rehearsals/{session.id}/1",
        size_bytes=2048,
        sha256="c" * 64,
        crc32c="AAAAAAA=",
        content_type="audio/wav",
    )
    db_session.add(rehearsal)
    await db_session.commit()
    joined.origin = rehearsal.id
    await db_session.commit()
    joined_at = joined.created_at
    desk, _user = await at_the_desk(
        db_session, room_app, await db_session.get(Project, TABLET_TEAM)
    )

    await laid_in_and_told_again(client, session.id, part_1[1].id, 1)
    await forced(client, desk, session)
    manifest = await manifest_of(client, desk, session)

    [clip] = [clip for clip in manifest["clips"] if clip["key"] == "S1"]
    assert clip["splices"] == 1
    assert clip["origin"]["joinedAt"] == joined_at.astimezone(UTC).isoformat()


async def test_a_part_with_a_sentence_laid_in_says_how_many_along_its_chain(
    client, db_session, room_app, store
):
    session, _takes, (part_1, _part_2) = await rehearsed_in_wav(db_session, store, [PART, PART])
    desk, _user = await at_the_desk(
        db_session, room_app, await db_session.get(Project, TABLET_TEAM)
    )

    await laid_in_and_told_again(client, session.id, part_1[1].id, 1)
    await forced(client, desk, session)
    first = await manifest_of(client, desk, session)
    await laid_in_and_told_again(
        client,
        session.id,
        part_1[2].id,
        2,
        sentence_id="sentence-0002",
        reopens_the_approved_draft=True,
    )
    await forced(client, desk, session)
    second = await manifest_of(client, desk, session)
    [spliced] = [
        take for take in current_parts(await takes_of(db_session, session.id)) if take.ordinal == 1
    ]
    await record_the_part_again(db_session, session, spliced, sha256="d" * 64)
    await forced(client, desk, session)
    third = await manifest_of(client, desk, session)

    assert first["clips"][0]["splices"] == 1
    assert "splices" not in first["clips"][1]
    assert second["clips"][0]["splices"] == 2
    assert "splices" not in third["clips"][0]


async def test_the_manifest_carries_no_frase_words_no_note_and_no_consultant_material(
    client, db_session, room_app
):
    session, desk = await planted_and_forced(client, db_session, room_app)

    manifest = await manifest_of(client, desk, session)

    carried = json.dumps(manifest, ensure_ascii=False)
    for planted in PLANTED:
        assert planted not in carried
    assert CONSULTANT_KEYS.isdisjoint(every_key(manifest))
    [nuance] = (await stored_telling_back(db_session, session)).nuances
    assert nuance.note == NUANCE_NOTE, "the control: the nuance's note is in the room's record"


async def test_what_the_manifest_leaves_out_is_in_the_retroverificacao_file(
    client, db_session, room_app
):
    session, desk = await planted_and_forced(client, db_session, room_app)

    retro = await client.get(desk_retro(session.id), headers=desk)
    record = await client.get(desk_release_at(session.id, 1), headers=desk)

    assert retro.status_code == 200, retro.text
    kept_for_the_consultant = json.dumps(retro.json(), ensure_ascii=False)
    for planted in (TOLD_WORDS, OLD_WORDS, FINDING_NOTE, NUANCE_QUOTE, NUANCE_STORY, ATTEMPT_NOTE):
        assert planted in kept_for_the_consultant
    assert record.status_code == 200, record.text
    stored = json.dumps(record.json(), ensure_ascii=False)
    assert TOLD_WORDS in stored
    assert OLD_WORDS in stored


async def test_a_superseded_take_never_reaches_the_manifest(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, parts = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    replaced = parts[0]
    again = await record_the_part_again(db_session, session, replaced, sha256="e" * 64)
    await tell_back_about(db_session, session, again, bridge_take_id="retro-novo")
    await a_checked_telling(db_session, session)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert [clip["key"] for clip in manifest["clips"]] == ["S1", "S2"]
    assert manifest["clips"][0]["takeId"] == again.id
    carried = json.dumps(manifest)
    assert replaced.id not in carried
    assert replaced.sha256 not in carried


async def test_the_check_lists_the_nuances_in_her_keys(
    client, analyst, speaker, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = "Só um detalhe, na frase 2: vocês traduziram de outro jeito."
    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    heard = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/heard",
        json={"at": pressed.json()["check_at"]},
    )
    assert heard.status_code == 200, heard.text
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)
    stored = (await client.get(desk_release_at(session.id, 1), headers=desk)).json()

    check = (await manifest_of(client, desk, session))["check"]

    assert list(check) == [*HER_CHECK_KEYS[:-1], "nuances", "retroUrl"]
    assert len(check["nuances"]) == 1
    assert check["nuances"] == stored["check"]["nuances"]
    assert check["status"] == "conferida"
    assert check["retroUrl"] == (
        f"/api/internalization-room/facilitator/sessions/{session.id}/retroverificacao"
    )


async def test_a_clean_check_carries_no_nuances_key(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    check = (await manifest_of(client, desk, session))["check"]

    assert list(check) == HER_CHECK_KEYS


async def test_a_forced_drafts_manifest_says_forcada_and_names_nobody(client, db_session, room_app):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    await forced(client, desk, session)

    manifest = await manifest_of(client, desk, session)

    check = manifest["check"]
    assert check["status"] == "forcada"
    assert check["forced"] is True
    for who in ("forcedBy", "forcedAt", "forcedBlockers"):
        assert who not in check
    assert facilitator.id not in json.dumps(manifest)


async def test_a_passage_never_approved_has_no_manifest(client, db_session, room_app):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 409, read.text
    assert read.json()["code"] == "DRAFT_NOT_APPROVED"


async def test_a_frase_told_after_the_approval_leaves_the_manifest_of_the_approved_version(
    client, db_session, room_app
):
    """Only a change of takes re-opens an approved draft (ADR 0081)."""
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    await one_stretch(db_session, session, text="e mais uma frase contada")
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert manifest["releaseId"] == "internalize-terena-p01-v1"


async def test_a_finding_raised_after_the_approval_leaves_the_manifest_of_the_approved_version(
    client, db_session, room_app
):
    """The gate is read only while no version stands: nothing but a take re-opens one."""
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    await reported_playback(
        db_session, session, await told_back_with_an_open_finding(db_session, session)
    )
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)
    read = await client.get(f"{PREFIX}/sessions/{session.id}", headers=team_headers(credential))

    assert manifest["releaseId"] == "internalize-terena-p01-v1"
    assert read.json()["approved"]["version"] == 1


async def test_a_force_over_a_standing_version_answers_it_and_records_no_force(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    await reported_playback(
        db_session, session, await told_back_with_an_open_finding(db_session, session)
    )
    desk, _user = await at_the_desk(db_session, room_app, project)

    answer = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert answer.status_code == 200, answer.text
    assert (answer.json()["version"], answer.json()["forced_at"]) == (1, None)
    assert len(await releases_of(db_session, session.id)) == 1


async def test_a_passage_the_gate_refuses_has_no_manifest(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    refused = await client.post(team_release(session.id), headers=team_headers(credential))
    assert refused.json()["blockers"] == ["telling_back_not_checked"], refused.text
    desk, _user = await at_the_desk(db_session, room_app, project)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 409, read.text
    assert read.json()["code"] == "DRAFT_NOT_APPROVED"


async def test_a_facilitator_of_another_team_is_not_told_the_manifest_exists(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    stranger, _other = await a_claimed_device(db_session, language_name="Kaiowá")
    desk, _user = await at_the_desk(db_session, room_app, stranger)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 404, read.text


async def test_the_sessions_are_the_teams_sessions_of_the_passage_sorted(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    await create_session(db_session, pericope=P01, project_id=project.id, language="pt")
    await archive_pericope(db_session, facilitator, project_id=project.id, pericope=P01)
    in_portuguese = await ready_p01(db_session, project.id, language="pt")
    in_english = await create_session(
        db_session, pericope=P01, project_id=project.id, language="en"
    )
    await create_session(db_session, pericope="P02", project_id=project.id, language="pt")
    other_team, _other = await a_claimed_device(db_session, language_name="Kaiowá")
    await create_session(db_session, pericope=P01, project_id=other_team.id, language="pt")
    await approved(client, credential, in_portuguese)

    manifest = await manifest_of(client, desk, in_portuguese)

    assert manifest["sessionIds"] == sorted([in_portuguese.id, in_english.id])


async def downloads_of(
    client: httpx.AsyncClient, desk: dict[str, str], session: IRSession
) -> dict[str, str]:
    listed = await client.get(
        f"{PREFIX}/facilitator/sessions/{session.id}/takes/downloads", headers=desk
    )
    assert listed.status_code == 200, listed.text
    return {each["take_id"]: each["filename"] for each in listed.json()["takes"]}


async def test_the_file_names_and_the_download_list_agree(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _sent = await p01_in_two_wav_parts(client, db_session, project.id, credential)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)
    listed = await downloads_of(client, desk, session)

    assert {clip["takeId"]: clip["filename"] for clip in manifest["clips"]} == listed


def in_the_old_shape(
    packet: dict[str, Any], *, named: bool, checked: bool, open_points: int = 0
) -> dict[str, Any]:
    """A packet as a schema before v0.7 stored it: with the comprehension block, before the
    takes carried a duration or a key and the frases a scene (ADR 0056, 0072, 0078); without
    Marcia's name and the keys beside it before ADR 0048, and without the check before ADR 0020.
    """
    old = {**packet, "schema_version": "tripod.internalization-release.v0.6"}
    old["comprehension"] = {
        "outcome": "ready_for_refine",
        "supported_unit_ids": ["S1"],
        "total_units": 1,
        "practiced_scene_ids": ["S1"],
        "events": [],
        "open_points": [
            {
                "unit_id": f"being:S1:B{n}",
                "reason": "not_yet_evidenced",
                "checkpoint_kind": "being",
                "scene_id": "S1",
                "source_id": f"B{n}",
                "canonical": "Noemi",
            }
            for n in range(1, open_points + 1)
        ],
    }
    old["open_questions"] = packet["open_questions"] + open_points
    old["audio"] = {
        **packet["audio"],
        "rehearsal_takes": [
            {k: v for k, v in take.items() if k not in ("key", "duration_ms")}
            for take in packet["audio"]["rehearsal_takes"]
        ],
    }
    old["back_translation"] = {
        **packet["back_translation"],
        "segments": [
            {k: v for k, v in frase.items() if k != "scene"}
            for frase in packet["back_translation"]["segments"]
        ],
    }
    if not named:
        for named_since_adr_0048 in ("release_id", "language", "session_language", "audio_format"):
            old.pop(named_since_adr_0048)
    if not checked:
        old.pop("check")
    return old


async def stored_in_the_old_shape(
    db: AsyncSession,
    session: IRSession,
    project: Project,
    *,
    named: bool,
    checked: bool,
    open_points: int = 0,
) -> str:
    packet = await judged_packet(db, session)
    packet["release_id"] = RUTH_P01_V1
    packet["version"] = 1
    packet["check"] = {**packet["check"], "version": 1}
    row_id = str(uuid.uuid4())
    db.add(
        IRRelease(
            id=row_id,
            session_id=session.id,
            project_id=project.id,
            pericope=P01,
            version=1,
            package_sha256=packet["package_sha256"],
            packet=in_the_old_shape(packet, named=named, checked=checked, open_points=open_points),
            device_id=TABLET,
        )
    )
    await db.commit()
    return row_id


async def test_a_release_stored_before_adr_0048_names_the_manifest_and_its_files_by_its_uuid(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _sent = await p01_in_two_wav_parts(client, db_session, project.id, credential)
    legacy_id = await stored_in_the_old_shape(
        db_session, session, project, named=False, checked=True
    )
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)
    listed = await downloads_of(client, desk, session)

    assert manifest["releaseId"] == legacy_id
    assert manifest["language"] == "Terena"
    assert {clip["takeId"]: clip["filename"] for clip in manifest["clips"]} == listed
    assert all(clip["filename"].startswith(f"{legacy_id}-") for clip in manifest["clips"])


async def test_a_passage_approved_under_a_schema_before_v0_7_still_gets_its_manifest(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _sent = await p01_in_two_wav_parts(client, db_session, project.id, credential)
    await stored_in_the_old_shape(db_session, session, project, named=True, checked=True)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert manifest["releaseId"] == RUTH_P01_V1
    assert manifest["check"]["status"] == "conferida"
    assert "warnings" not in manifest


async def test_a_v0_6_approval_whose_comprehension_left_open_points_still_gets_its_manifest(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _sent = await p01_in_two_wav_parts(client, db_session, project.id, credential)
    await stored_in_the_old_shape(
        db_session, session, project, named=True, checked=True, open_points=2
    )
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert manifest["releaseId"] == RUTH_P01_V1


async def test_a_passage_approved_before_the_check_was_recorded_gets_her_warning(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _sent = await p01_in_two_wav_parts(client, db_session, project.id, credential)
    await stored_in_the_old_shape(db_session, session, project, named=True, checked=False)
    desk, _user = await at_the_desk(db_session, room_app, project)

    manifest = await manifest_of(client, desk, session)

    assert manifest["check"] is None
    assert manifest["warnings"] == [
        "this release was approved before the approval record existed: no check state "
        "(conferida / forçada / findings) is recorded for it"
    ]


async def test_a_passage_whose_canon_is_gone_is_refused_by_its_canon_and_not_as_unapproved(
    client, db_session, room_app, monkeypatch, tmp_path: Path
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)
    shutil.rmtree(the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN))

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 409, read.text
    assert read.json()["code"] == "CANON_NOT_KEPT"
    assert session.canon_pin in read.json()["detail"]


async def test_a_take_that_lands_after_the_approval_is_judged_is_never_listed_as_approved(
    client, db_session, room_app, monkeypatch
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, parts = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    await a_checked_telling(db_session, session)
    await approved(client, credential, session)
    desk, _user = await at_the_desk(db_session, room_app, project)
    landed = []
    judged = manifest_service.approved_draft

    async def and_then_a_take_lands(db: AsyncSession, judging: IRSession) -> IRRelease | None:
        release = await judged(db, judging)
        landed.append(await record_the_part_again(db, judging, parts[0], sha256="d" * 64))
        return release

    monkeypatch.setattr(manifest_service, "approved_draft", and_then_a_take_lands)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 409, read.text
    assert read.json()["code"] == "DRAFT_NOT_APPROVED"
    assert landed[0].id not in read.text


async def test_a_zerar_retires_the_approval_until_the_new_session_approves(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    zeroed = await ready_p01(db_session, project.id)
    await approved(client, credential, zeroed)
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    await archive_pericope(db_session, facilitator, project_id=project.id, pericope=P01)

    retired = await client.get(desk_release(zeroed.id), headers=desk)

    assert retired.status_code == 409, retired.text
    assert retired.json()["code"] == "DRAFT_NOT_APPROVED"
    assert P01 not in await standing_approvals(db_session, project.id)
    kept = await client.get(desk_release_at(zeroed.id, 1), headers=desk)
    assert kept.status_code == 200, kept.text

    again = await ready_p01(db_session, project.id)
    await approved(client, credential, again)
    manifest = await manifest_of(client, desk, again)

    assert manifest["releaseId"] == "internalize-terena-p01-v2"
    assert manifest["finalizeCount"] == 2


async def test_a_panorama_is_refused_as_a_panorama_before_any_canon_is_read(
    client, db_session, room_app
):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    panorama = await create_session(db_session, pericope="OV", project_id=project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    read = await client.get(desk_release(panorama.id), headers=desk)

    assert read.status_code == 409, read.text
    assert read.json()["code"] == "CONFLICT"
    assert "panorama_sessions_never_release" in read.json()["detail"]


async def test_a_release_stored_as_a_force_that_waived_nothing_reads_as_an_ordinary_approval(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_p01(db_session, project.id)
    await approved(client, credential, session)
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    row = await db_session.scalar(select(IRRelease).where(IRRelease.session_id == session.id))
    assert row is not None
    row.forced_by = facilitator.id
    row.forced_at = datetime(2026, 10, 1, 14, 10, tzinfo=UTC)
    row.forced_blockers = []
    row.packet = {**row.packet, "check": {**row.packet["check"], "forced": True}}
    await db_session.commit()

    manifest = await manifest_of(client, desk, session)

    assert (manifest["check"]["forced"], manifest["check"]["status"]) == (False, "conferida")
    assert facilitator.id not in json.dumps(manifest)
