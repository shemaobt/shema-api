"""ENG-1211 — the release tells Refine the team's mother tongue and the session language.

The packet named no language, and its ``release_id`` was the row's uuid, so a Refine reader
could not tell whose rehearsal it held or which draft Marcia's check was hearing. The packet
now states the mother tongue, the language the room spoke and whether every rehearsal part is
WAV, and a new release is named the way her app names it. Expected values come from the ticket
and from her ``export.ts``: ``internalize-<slug(language)>-<pericope lower>-v<version>``.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App
from app.db.models.internalization_room import IRRelease, IRSession
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.release import build_internalization_release
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import create_session
from tests.baker import (
    make_app,
    make_role,
)
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    PREFIX,
    TABLET,
    P,
    a_claimed_device,
    at_the_desk,
    desk_release,
    desk_release_at,
    ready_session,
    releases_of,
    reported_playback,
    team_headers,
    team_release,
    the_one_part_of,
    told_back_with_an_open_finding,
)
from tests.room_harness import (
    rehearsed_in_parts,
    room_client,
    the_bucket_is_in_memory,
    upload_a_part,
)

BUCKET = "balde-de-teste"
STORAGE = "https://armazenamento.exemplo"

WAV_FORMAT = {"container": "wav", "codec": "pcm_s16le", "sample_rate": 16000, "channels": 1}
OUTSIDE_THE_FINGERPRINT = (
    "package_sha256",
    "release_id",
    "version",
    "created_at",
    "check",
    "language",
    "session_language",
    "audio_format",
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings

    the_bucket_is_in_memory(monkeypatch)
    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", BUCKET, raising=False)

    async def _signed(bucket: str, key: str, **_kwargs: object) -> str:
        return f"{STORAGE}/{bucket}/{key}?assinado"

    monkeypatch.setattr(takes_service, "generate_signed_download_url", _signed)
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession) -> App:
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def ready_in(
    db: AsyncSession,
    project_id: str | None,
    *,
    language: str = "pt",
    content_types: tuple[str, ...] = ("audio/mp4",),
    audio: tuple[bytes, ...] | None = None,
) -> IRSession:
    """A session ready to approve, rehearsed in one part per content type given."""
    session, _parts = await rehearsed_in_parts(
        db,
        len(content_types),
        project_id=project_id,
        language=language,
        content_types=content_types,
        audio=audio,
    )
    told = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=P, findings=[], checked=True, analysed_segment_ids=[stretch.id for stretch in told]
    )
    await reported_playback(db, session, state)
    return session


async def approved(client, credential: str, session: IRSession):
    answer = await client.post(team_release(session.id), headers=team_headers(credential))
    assert answer.status_code == 200, answer.text
    return answer.json()


async def stored_packet(client, db, room_app, project, session, version: int = 1) -> dict:
    desk, _user = await at_the_desk(db, room_app, project)
    read = await client.get(desk_release_at(session.id, version), headers=desk)
    assert read.status_code == 200, read.text
    return read.json()


async def test_a_terena_team_in_portuguese_says_mother_tongue_terena_and_session_language_pt(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id, language="pt")

    await approved(client, credential, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert packet["language"] == "Terena"
    assert packet["session_language"] == "pt"


async def test_the_release_of_a_terena_team_is_named_internalize_terena_pericope_v1(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id)

    body = await approved(client, credential, session)

    assert body["release_id"] == "internalize-terena-p03-v1"
    packet = await stored_packet(client, db_session, room_app, project, session)
    assert packet["release_id"] == "internalize-terena-p03-v1"


async def test_a_later_passage_in_english_says_session_language_en_and_mother_tongue_terena(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    first = await ready_in(db_session, project.id, language="pt")
    await approved(client, credential, first)
    later = await ready_in(db_session, project.id, language="en")

    await approved(client, credential, later)

    packet = await stored_packet(client, db_session, room_app, project, later, version=2)
    assert packet["session_language"] == "en"
    assert packet["language"] == "Terena"


async def test_two_teams_on_one_passage_each_name_their_own_mother_tongue(
    client, db_session, room_app
):
    terena, terena_credential = await a_claimed_device(db_session, language_name="Terena")
    guarani, guarani_credential = await a_claimed_device(
        db_session, email="guarani@example.com", language_name="Guarani"
    )
    terena_session = await ready_in(db_session, terena.id)
    guarani_session = await ready_in(db_session, guarani.id)

    await approved(client, terena_credential, terena_session)
    await approved(client, guarani_credential, guarani_session)

    terena_packet = await stored_packet(client, db_session, room_app, terena, terena_session)
    guarani_packet = await stored_packet(client, db_session, room_app, guarani, guarani_session)
    assert terena_packet["language"] == "Terena"
    assert terena_packet["release_id"] == "internalize-terena-p03-v1"
    assert guarani_packet["language"] == "Guarani"
    assert guarani_packet["release_id"] == "internalize-guarani-p03-v1"


async def test_a_mother_tongue_with_accents_and_spaces_is_named_by_her_slug(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terêna Ñandeva")
    session = await ready_in(db_session, project.id)

    body = await approved(client, credential, session)

    assert body["release_id"] == "internalize-terena-nandeva-p03-v1"


async def test_a_mother_tongue_whose_name_leaves_nothing_to_slug_is_named_lrl(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Терена")
    session = await ready_in(db_session, project.id)

    body = await approved(client, credential, session)

    assert "-lrl-" in body["release_id"]
    packet = await stored_packet(client, db_session, room_app, project, session)
    assert packet["language"] == "Терена"


async def test_a_session_that_names_no_team_composes_a_packet_whose_language_is_null(db_session):
    session = await ready_session(db_session, project_id=None)

    packet = await build_internalization_release(db_session, session)

    assert packet["language"] is None


async def test_the_second_release_of_a_passage_is_named_v2(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id)
    await approved(client, credential, session)
    await capture_segment(
        db_session,
        session,
        take_id=(await the_one_part_of(db_session, session)).id,
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id="retro-novo",
        transcript="uma frase a mais, contada de volta",
    )

    body = await approved(client, credential, session)

    assert body["version"] == 2
    assert body["release_id"] == "internalize-terena-p03-v2"


async def test_approving_an_unchanged_passage_again_returns_the_same_release_and_the_same_name(
    client, db_session
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id)

    first = await approved(client, credential, session)
    again = await approved(client, credential, session)

    assert again["version"] == first["version"] == 1
    assert again["release_id"] == first["release_id"] == "internalize-terena-p03-v1"
    assert len(await releases_of(db_session, session.id)) == 1


async def test_the_new_keys_sit_outside_the_fingerprint(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id)
    await approved(client, credential, session)

    packet = await stored_packet(client, db_session, room_app, project, session)

    assert {"language", "session_language", "audio_format"} <= packet.keys()
    hashed = {k: v for k, v in packet.items() if k not in OUTSIDE_THE_FINGERPRINT}
    canonical = json.dumps(hashed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == packet["package_sha256"]


async def test_a_release_stored_before_this_deploy_is_returned_unchanged_on_approval(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id)
    packet = await build_internalization_release(db_session, session)
    legacy_id = str(uuid.uuid4())
    for key in ("language", "session_language", "audio_format"):
        packet.pop(key, None)
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

    body = await approved(client, credential, session)

    assert body["version"] == 1
    assert body["release_id"] == legacy_id
    assert len(await releases_of(db_session, session.id)) == 1
    served = await stored_packet(client, db_session, room_app, project, session)
    assert not {"language", "session_language", "audio_format"} & served.keys()


async def test_the_desks_live_read_names_the_approved_release_by_its_stored_name(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    before = await client.get(desk_release(session.id), headers=desk)
    assert before.json()["release_id"] is None
    await approved(client, credential, session)
    after = await client.get(desk_release(session.id), headers=desk)

    assert after.json()["release_id"] == "internalize-terena-p03-v1"


async def test_a_release_whose_every_rehearsal_part_is_wav_states_the_wav_audio_format(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id, content_types=("audio/wav", "audio/wav"))

    await approved(client, credential, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert packet["audio_format"] == WAV_FORMAT


async def test_a_release_with_one_m4a_part_states_no_audio_format(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_in(db_session, project.id, content_types=("audio/wav", "audio/mp4"))

    await approved(client, credential, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert packet["audio_format"] is None


async def _download_location(client, db, credential, project, content_type: str) -> str:
    session = await create_session(db, pericope=P, project_id=project.id, language="pt")
    uploaded = await upload_a_part(
        client,
        session.id,
        part=1,
        audio=b"a equipe gravou a cena " + content_type.encode(),
        content_type=content_type,
        headers=team_headers(credential),
    )
    assert uploaded.status_code == 200, uploaded.text
    heard = await client.get(
        f"{PREFIX}/sessions/{session.id}/takes/{uploaded.json()['take_id']}/audio",
        headers=team_headers(credential),
        follow_redirects=False,
    )
    assert heard.status_code == 307, heard.text
    return heard.headers["location"]


async def test_a_wav_take_downloads_under_a_wav_name(client, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")

    location = await _download_location(client, db_session, credential, project, "audio/wav")

    assert location.split("?")[0].endswith("/tomada.wav")


async def test_an_m4a_take_still_downloads_under_its_m4a_name(client, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")

    location = await _download_location(client, db_session, credential, project, "audio/mp4")

    assert location.split("?")[0].endswith("/tomada.m4a")


async def test_the_force_answers_the_release_by_its_name(client, db_session, room_app):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_session(
        db_session, project_id=project.id, tell=told_back_with_an_open_finding
    )
    desk, _user = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert forced.status_code == 200, forced.text
    assert forced.json()["release_id"] == "internalize-terena-p03-v1"
    packet = await stored_packet(client, db_session, room_app, project, session)
    assert packet["release_id"] == "internalize-terena-p03-v1"


async def test_a_take_resent_under_another_content_type_is_the_same_take_and_mints_no_new_version(
    client, db_session
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    audio = b"a equipe gravou a cena inteira"
    session = await ready_in(db_session, project.id, audio=(audio,))
    part = await the_one_part_of(db_session, session)
    first = await approved(client, credential, session)

    resent = await upload_a_part(
        client,
        session.id,
        part=1,
        audio=audio,
        content_type="audio/wav",
        headers=team_headers(credential),
    )

    assert resent.status_code == 200, resent.text
    assert resent.json()["take_id"] == part.id
    again = await approved(client, credential, session)
    assert again["version"] == first["version"] == 1
    assert len(await releases_of(db_session, session.id)) == 1
