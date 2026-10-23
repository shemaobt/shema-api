"""ENG-1258 — an approved draft is internalize-<lang>-<passage>-v<N> with her record and nuances.

Each approved **Version** keeps Marcia's approval record: its name, each pinned take with its
duration and its **Part key**, each frase and each finding with the scene of the part it stands
on, each finding with a whole-number `index`, and the **Nuances** the check found with whether
the voice said them. A check whose only findings are nuances is conferida.

Expected values come from the ticket, the Definer's Definition of 2026-10-19 and her
`ApprovalFinding` (Tripod-Internalization 18fa7c4, src/draft/store.ts). Every case reads the
packet the Desk reads back by version, which is the record as it was stored.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import back_translation as bt_api
from app.db.models.auth import App
from app.db.models.internalization_room import IRRelease, IRSession
from app.db.models.language import Language
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
    Nuance,
)
from app.services.internalization_room.canon.scene_ids import scene_ids_for
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import create_session, get_session
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    PREFIX,
    TABLET,
    P,
    a_claimed_device,
    at_the_desk,
    checked_telling_back,
    desk_release,
    desk_release_at,
    ensaio_take,
    judged_packet,
    ready_session,
    releases_of,
    reported_playback,
    team_headers,
    team_release,
    the_part_recorded_again,
    told_back_with_an_open_finding,
)
from tests.room_harness import (
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
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
from tests.turn_harness import the_room_agent_is

BUCKET = "balde-de-teste"
STORAGE = "https://armazenamento.exemplo"

ON_FRASE_2 = {
    "kind": "nuance",
    "note": "NOTA-DA-NUANCE-7e1a",
    "frase": 2,
    "quote": "contada de volta",
    "story": "HISTORIA-DA-NUANCE-7e1a",
}
ON_FRASE_3 = {
    "kind": "nuance",
    "note": "A parte ficou solta.",
    "frase": 3,
    "quote": "parte 2",
    "story": "a história diz qual parte",
}
NAMES_FRASE_2 = "Só um detalhe, na frase 2: vocês traduziram de outro jeito."
NAMES_FRASE_3 = "Só um detalhe, na frase 3: vocês disseram de outro jeito."


class Speaker:
    def __init__(self) -> None:
        self.line = "Vocês contaram bem."

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.line


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


@pytest.fixture()
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    nothing_is_read_ahead(monkeypatch)

    async def said(*_: Any, **__: Any) -> str:
        return "a equipe contou o trecho de volta"

    monkeypatch.setattr(bt_api, "heard", said)


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch):
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    the_room_speaks(monkeypatch)
    voice = Speaker()
    the_room_agent_is(monkeypatch, turn=voice)
    return voice


async def approved(client, credential: str, session: IRSession) -> dict[str, Any]:
    answer = await client.post(team_release(session.id), headers=team_headers(credential))
    assert answer.status_code == 200, answer.text
    return answer.json()


async def forced(client, db, room_app, project, session: IRSession) -> None:
    desk, _user = await at_the_desk(db, room_app, project)
    answer = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert answer.status_code == 200, answer.text


async def stored_packet(client, db, room_app, project, session, version: int = 1) -> dict:
    desk, _user = await at_the_desk(db, room_app, project)
    read = await client.get(desk_release_at(session.id, version), headers=desk)
    assert read.status_code == 200, read.text
    return read.json()


async def read_with(db: AsyncSession, session: IRSession, findings: list[Finding]) -> None:
    """The state one reading that raised these findings leaves behind, stored with the report."""
    told = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=P,
        findings=findings,
        checked=not findings,
        analysed_segment_ids=[stretch.id for stretch in told],
    )
    await reported_playback(db, session, state)


def an_addition_on(segment_id: str | None) -> Finding:
    """An addition the analyst numbered 9, a number no frase here has: the record reads its own."""
    return Finding(
        kind=FindingKind.ADDITION,
        note="a equipe pôs algo a mais",
        segment_id=segment_id,
        chunk=9,
    )


def keys_of_the_takes(packet: dict) -> list[str | None]:
    return [take.get("key") for take in packet["audio"]["rehearsal_takes"]]


def scenes_of_the_frases(packet: dict) -> list[tuple[int, str | None]]:
    segments = packet["back_translation"]["segments"]
    return [(frase["frase"], frase.get("scene")) for frase in segments]


async def test_the_first_approval_of_a_terena_teams_p01_is_named_internalize_terena_p01_v1(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_session(db_session, pericope="P01", project_id=project.id)

    body = await approved(client, credential, session)

    assert body["release_id"] == "internalize-terena-p01-v1"
    assert body["version"] == 1
    packet = await stored_packet(client, db_session, room_app, project, session)
    assert packet["release_id"] == "internalize-terena-p01-v1"
    assert packet["version"] == 1


async def test_a_second_approval_of_the_same_passage_is_named_v2(client, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_session(db_session, pericope="P01", project_id=project.id)
    await approved(client, credential, session)
    await the_part_recorded_again(db_session, session)
    await reported_playback(db_session, session, await checked_telling_back(db_session, session))

    body = await approved(client, credential, session)

    assert body["release_id"] == "internalize-terena-p01-v2"
    assert body["version"] == 2


async def test_a_team_whose_mother_tongue_is_empty_names_its_release_lrl(client, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    await db_session.execute(
        update(Language).where(Language.id == project.language_id).values(name="")
    )
    await db_session.commit()
    session = await ready_session(db_session, project_id=project.id)

    body = await approved(client, credential, session)

    assert body["release_id"] == "internalize-lrl-p03-v1"


async def test_the_approval_record_gives_every_pinned_take_its_duration_and_key_and_every_finding_its_index_and_scene(  # noqa: E501
    client, db_session, room_app, quiet
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await create_session(db_session, pericope=P, project_id=project.id, language="pt")
    sent = []
    for part, (seconds, tone) in enumerate(((3, 1), (2.5, 2), (2, 3)), start=1):
        answer = await upload_a_part(
            client,
            session.id,
            part=part,
            audio=recording(seconds, tone),
            content_type="audio/wav",
            headers=team_headers(credential),
        )
        assert answer.status_code == 200, answer.text
        sent.append(answer.json())
    session = await get_session(db_session, session.id)
    for index, take in enumerate(sent):
        await capture_segment(
            db_session,
            session,
            take_id=take["take_id"],
            starts_ms=0,
            ends_ms=take["duration_ms"],
            bridge_take_id=f"retro-{index}",
            transcript=f"parte {index} contada de volta",
        )
    told = await final_segments(db_session, session.id)
    await read_with(db_session, session, [an_addition_on(told[1].id)])

    await forced(client, db_session, room_app, project, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert [(take["duration_ms"], take["key"]) for take in packet["audio"]["rehearsal_takes"]] == [
        (3000, "S1"),
        (2500, "S2"),
        (2000, "S3"),
    ]
    segments = packet["back_translation"]["segments"]
    assert scenes_of_the_frases(packet) == [(1, "S1"), (2, "S2"), (3, "S3")]
    assert all({"starts_ms", "ends_ms"} <= frase.keys() for frase in segments)
    assert packet["check"]["findings"] == [
        {
            "kind": "addition",
            "idx": told[1].id,
            "clipKey": sent[1]["take_id"],
            "frase": 2,
            "index": 2,
            "scene": "S2",
        }
    ]
    assert packet["schema_version"] == "tripod.internalization-release.v0.9"


async def test_a_rehearsal_told_whole_is_the_scene_whole(client, db_session, room_app):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_session(
        db_session, project_id=project.id, tell=told_back_with_an_open_finding
    )

    await forced(client, db_session, room_app, project, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert keys_of_the_takes(packet) == ["whole"]
    assert scenes_of_the_frases(packet) == [(1, "whole")]
    assert [finding.get("scene") for finding in packet["check"]["findings"]] == ["whole"]


async def test_the_part_key_follows_the_parts_position_not_its_stored_number(
    client, db_session, room_app
):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session, parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    for part, stored_as in zip(parts, (0, 4, 9), strict=True):
        part.ordinal = stored_as
    await db_session.commit()
    told = await final_segments(db_session, session.id)
    await read_with(db_session, session, [an_addition_on(told[0].id)])

    await forced(client, db_session, room_app, project, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert keys_of_the_takes(packet) == ["S1", "S2", "S3"]
    assert scenes_of_the_frases(packet) == [(1, "S1"), (2, "S2"), (3, "S3")]
    assert [finding.get("scene") for finding in packet["check"]["findings"]] == ["S1"]


async def test_a_part_past_the_passages_last_scene_reads_the_key_of_its_position(
    client, db_session, room_app
):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    assert len(scene_ids_for(P)) == 3
    session, _parts = await rehearsed_in_parts(db_session, 4, project_id=project.id)
    told = await final_segments(db_session, session.id)
    await read_with(db_session, session, [an_addition_on(told[3].id)])

    await forced(client, db_session, room_app, project, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert keys_of_the_takes(packet) == ["S1", "S2", "S3", "S4"]
    assert scenes_of_the_frases(packet) == [(1, "S1"), (2, "S2"), (3, "S3"), (4, "S4")]
    assert [finding.get("scene") for finding in packet["check"]["findings"]] == ["S4"]


async def test_a_finding_on_no_stretch_of_the_reading_has_no_index_and_no_scene(
    client, db_session, room_app
):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    await read_with(db_session, session, [an_addition_on(None)])

    await forced(client, db_session, room_app, project, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert packet["check"]["findings"] == [{"kind": "addition", "idx": None, "clipKey": None}]


async def test_a_check_with_only_a_nuance_is_conferida_and_its_approval_carries_the_nuance_said_now(
    client, analyst, speaker, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    frase_2 = (await final_segments(db_session, session.id))[1]
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2

    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    await heard_to_its_end(client, session, pressed)
    body = await approved(client, credential, session)

    assert pressed.json()["checked"] is True, pressed.text
    assert body["version"] == 1
    assert body["blockers"] == []
    check = (await stored_packet(client, db_session, room_app, project, session))["check"]
    assert check["conferida"] is True
    assert check["status"] == "conferida"
    assert check["findings"] == []
    assert check["nuances"] == [
        {
            "kind": "nuance",
            "idx": frase_2.id,
            "clipKey": parts[1].id,
            "frase": 2,
            "index": 2,
            "scene": "S2",
            "voiced": "now",
        }
    ]


async def test_the_checks_own_round_keeps_the_nuance_it_said(client, analyst, speaker, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    frase_2 = (await final_segments(db_session, session.id))[1]
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2

    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))

    last = (await stored_telling_back(db_session, session)).checks[-1]
    assert [(one.segment_id, one.voiced) for one in last.nuances] == [(frase_2.id, "now")]


async def test_a_nuance_the_voice_never_said_carries_no_voiced(
    client, analyst, speaker, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    analyst.readings = [{"findings": [ON_FRASE_2]}]

    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))
    body = await approved(client, credential, session)

    assert body["version"] == 1
    check = (await stored_packet(client, db_session, room_app, project, session))["check"]
    assert check["conferida"] is True
    [nuance] = check["nuances"]
    assert nuance["frase"] == 2
    assert "voiced" not in nuance


async def test_a_nuance_a_verdict_named_but_the_team_never_heard_is_not_said(
    client, analyst, speaker, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2

    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))
    await approved(client, credential, session)

    check = (await stored_packet(client, db_session, room_app, project, session))["check"]
    [nuance] = check["nuances"]
    assert nuance["frase"] == 2
    assert "voiced" not in nuance


async def test_a_nuance_said_in_an_earlier_check_reads_before(
    client, analyst, speaker, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    report = await heard_every_part(db_session, session.id)
    analyst.readings = [{"findings": [ON_FRASE_3, ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    first = await press_terminei(client, session.id, report=report)
    await heard_to_its_end(client, session, first)
    speaker.line = NAMES_FRASE_3
    second = await press_terminei(client, session.id, report=report)
    await heard_to_its_end(client, session, second)

    await approved(client, credential, session)

    check = (await stored_packet(client, db_session, room_app, project, session))["check"]
    assert [(one["frase"], one.get("voiced")) for one in check["nuances"]] == [
        (2, "before"),
        (3, "now"),
    ]


async def test_two_nuances_in_the_same_words_on_one_frase_both_read_said_now(
    client, analyst, speaker, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    analyst.readings = [{"findings": [ON_FRASE_2, {**ON_FRASE_2, "note": "Outro olhar."}]}]
    speaker.line = NAMES_FRASE_2
    pressed = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    await heard_to_its_end(client, session, pressed)

    await approved(client, credential, session)

    check = (await stored_packet(client, db_session, room_app, project, session))["check"]
    assert [(one["frase"], one.get("voiced")) for one in check["nuances"]] == [
        (2, "now"),
        (2, "now"),
    ]


async def test_a_nuance_on_a_whole_recording_set_aside_by_parts_leaves_the_record(
    client, db_session, room_app
):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_session(db_session, project_id=project.id)
    whole = (await final_segments(db_session, session.id))[0]
    nuance = Nuance(
        note="O jeito de contar mudou.",
        chunk=1,
        segment_id=whole.id,
        quote="Noemi voltou",
        story="a história conta de outro jeito",
        take_id=whole.take_id,
        starts_ms=whole.starts_ms,
        ends_ms=whole.ends_ms,
    )
    state = BackTranslationState(
        scope=P,
        findings=[],
        nuances=[nuance],
        checked=True,
        analysed_segment_ids=[whole.id],
    )
    await reported_playback(db_session, session, state)
    part = ensaio_take(
        session.id, scope="parte-1", ordinal=1, sha256="b" * 64, project_id=project.id
    )
    db_session.add(part)
    await db_session.commit()
    await tell_back_about(db_session, session, part, bridge_take_id="retro-parte-1")

    await forced(client, db_session, room_app, project, session)

    packet = await stored_packet(client, db_session, room_app, project, session)
    assert keys_of_the_takes(packet) == ["S1"]
    assert packet["check"]["nuances"] == []


async def test_the_approval_record_never_carries_a_nuances_quote_story_or_note(
    client, analyst, speaker, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))

    await approved(client, credential, session)

    check = (await stored_packet(client, db_session, room_app, project, session))["check"]
    assert len(check["nuances"]) == 1
    carried = json.dumps(check, ensure_ascii=False)
    for words in (ON_FRASE_2["quote"], ON_FRASE_2["story"], ON_FRASE_2["note"]):
        assert words not in carried


async def test_a_nuances_voice_never_unapproves_the_draft(client, analyst, speaker, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    report = await heard_every_part(db_session, session.id)
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    first = await press_terminei(client, session.id, report=report)
    await heard_to_its_end(client, session, first)
    await approved(client, credential, session)
    await press_terminei(client, session.id, report=report)
    last = (await stored_telling_back(db_session, session)).checks[-1]
    assert [one.voiced for one in last.nuances] == ["before"]

    again = await approved(client, credential, session)

    assert again["version"] == 1


async def heard_to_its_end(client, session: IRSession, pressed) -> None:
    heard = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/heard",
        json={"at": pressed.json()["check_at"]},
    )
    assert heard.status_code == 200, heard.text


async def test_a_release_stored_before_this_ticket_keeps_its_packet(client, db_session, room_app):
    project, _credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_session(db_session, project_id=project.id)
    packet = await judged_packet(db_session, session)
    packet["schema_version"] = "tripod.internalization-release.v0.7"
    packet["check"].pop("nuances", None)
    for entry in packet["audio"]["rehearsal_takes"]:
        entry.pop("key", None)
    for entry in packet["back_translation"]["segments"]:
        entry.pop("scene", None)
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

    served = await stored_packet(client, db_session, room_app, project, session)

    assert served == packet


#: The keys the published hash leaves out (ADR 0020, ADR 0048): a v0.8 packet's own
#: ``package_sha256`` is the hash of the rest, as that schema stored it.
OUTSIDE_THE_PUBLISHED_HASH = (
    "package_sha256",
    "release_id",
    "version",
    "created_at",
    "check",
    "language",
    "session_language",
    "audio_format",
)


def published_hash(packet: dict) -> str:
    hashed = {k: v for k, v in packet.items() if k not in OUTSIDE_THE_PUBLISHED_HASH}
    canonical = json.dumps(hashed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def stored_with(db: AsyncSession, session: IRSession, change) -> None:
    """Rewrite this session's one stored release by `change`, as if it had been approved so."""
    [row] = await releases_of(db, session.id)
    packet = copy.deepcopy(row.packet)
    change(packet)
    row.packet = packet
    row.package_sha256 = packet["package_sha256"]
    await db.commit()


async def stored_under_v08(db: AsyncSession, session: IRSession) -> None:
    """Rewrite this session's one release as the v0.8 deploy stored it: no part keys, scenes,
    indexes or nuances, and the published hash that schema gave it."""
    await stored_with(db, session, as_v08)


def as_v08(packet: dict) -> None:
    packet["schema_version"] = "tripod.internalization-release.v0.8"
    for take in packet["audio"]["rehearsal_takes"]:
        take.pop("key")
    for frase in packet["back_translation"]["segments"]:
        frase.pop("scene", None)
    packet["check"].pop("nuances")
    for finding in packet["check"]["findings"]:
        finding.pop("index", None)
        finding.pop("scene", None)
    packet["package_sha256"] = published_hash(packet)


async def approved_on_the_tablet(client, credential: str, session: IRSession) -> Any:
    read = await client.get(f"{PREFIX}/sessions/{session.id}", headers=team_headers(credential))
    assert read.status_code == 200, read.text[:300]
    return read.json()["approved"]


async def a_clean_draft_approved(client, db: AsyncSession, project, credential: str) -> IRSession:
    session, _parts = await rehearsed_in_parts(db, 3, project_id=project.id)
    await read_with(db, session, [])
    await approved(client, credential, session)
    return session


async def test_one_draft_under_two_schema_versions_is_one_approved_draft(
    client, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_clean_draft_approved(client, db_session, project, credential)
    [row] = await releases_of(db_session, session.id)
    approved_under_v09 = row.package_sha256
    await stored_under_v08(db_session, session)
    [row] = await releases_of(db_session, session.id)
    assert row.package_sha256 != approved_under_v09, "the control: the hashes differ"

    again = await approved(client, credential, session)

    assert again["version"] == 1
    assert len(await releases_of(db_session, session.id)) == 1


async def test_a_draft_approved_under_v08_reads_approved_under_v09(client, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_clean_draft_approved(client, db_session, project, credential)

    await stored_under_v08(db_session, session)

    read = await approved_on_the_tablet(client, credential, session)
    assert read["version"] == 1


async def test_a_forced_v08_approval_stays_forced_and_approved(client, db_session, room_app):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await ready_session(
        db_session, project_id=project.id, tell=told_back_with_an_open_finding
    )
    await forced(client, db_session, room_app, project, session)

    await stored_under_v08(db_session, session)

    read = await approved_on_the_tablet(client, credential, session)
    assert (read["version"], read["forced"]) == (1, True)
    again = await approved(client, credential, session)
    assert (again["version"], again["blockers"]) == (1, [])


async def test_a_new_take_still_unapproves_a_draft_approved_under_v08(client, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_clean_draft_approved(client, db_session, project, credential)
    await stored_under_v08(db_session, session)

    again = await upload_a_part(
        client,
        session.id,
        part=2,
        audio=b"a segunda parte, gravada de novo",
        headers=team_headers(credential),
    )

    assert again.status_code == 200, again.text
    assert await approved_on_the_tablet(client, credential, session) is None


async def test_a_v08_approval_with_a_nuance_standing_today_reads_approved(
    client, analyst, speaker, db_session
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))
    await approved(client, credential, session)

    await stored_under_v08(db_session, session)

    assert (await approved_on_the_tablet(client, credential, session))["version"] == 1
    assert (await approved(client, credential, session))["version"] == 1


async def test_a_nuance_said_before_a_fail_safe_round_reads_before_on_a_forced_approval(
    client, analyst, speaker, db_session, room_app
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    analyst.readings = [{"findings": [ON_FRASE_2]}, {"findings": "ilegível"}]
    speaker.line = NAMES_FRASE_2
    first = await press_terminei(
        client, session.id, report=await heard_every_part(db_session, session.id)
    )
    await heard_to_its_end(client, session, first)
    await capture_segment(
        db_session,
        await get_session(db_session, session.id),
        take_id=parts[2].id,
        starts_ms=CLIP_MS,
        ends_ms=CLIP_MS + 1000,
        bridge_take_id="retro-nova",
        transcript="uma frase nova, contada de volta",
    )
    longer = await heard_every_part(db_session, session.id, duration_ms=CLIP_MS + 1000)
    await press_terminei(client, session.id, report=longer)
    last = (await stored_telling_back(db_session, session)).checks[-1]
    assert last.outcome == "fail_safe", "the control: the last round read nothing"

    await forced(client, db_session, room_app, project, session)

    check = (await stored_packet(client, db_session, room_app, project, session))["check"]
    assert [(one["frase"], one.get("voiced")) for one in check["nuances"]] == [(2, "before")]


async def test_a_listening_gap_filled_after_approval_leaves_the_draft_approved(client, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    told = await final_segments(db_session, session.id)
    state = BackTranslationState(
        scope=P, findings=[], checked=True, analysed_segment_ids=[one.id for one in told]
    )
    a_gap = [[0, 20000], [20500, CLIP_MS]]
    await reported_playback(db_session, session, state, played_ranges=a_gap)
    assert (await approved(client, credential, session))["version"] == 1, "the gap is tolerated"

    filled = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/listened-whole",
        json=await heard_every_part(db_session, session.id),
        headers=team_headers(credential),
    )

    assert filled.status_code == 200, filled.text
    assert (await approved_on_the_tablet(client, credential, session))["version"] == 1
    assert (await approved(client, credential, session))["version"] == 1


async def test_one_draft_under_two_canon_pins_is_one_approved_draft(client, db_session):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_clean_draft_approved(client, db_session, project, credential)

    await stored_with(
        db_session, session, lambda packet: packet.update(canon_vendor_pin="um-pin-anterior")
    )

    assert (await approved_on_the_tablet(client, credential, session))["version"] == 1
    assert (await approved(client, credential, session))["version"] == 1


def another_question(packet: dict) -> None:
    packet["raised_questions"].append(
        {"question_id": "outra-pergunta", "status": "resolved", "asked_at": None}
    )


def another_finding(packet: dict) -> None:
    packet["back_translation"]["findings"].append(
        {"kind": "addition", "segment_id": None, "chunk": 9}
    )


def another_take(packet: dict) -> None:
    packet["audio"]["rehearsal_takes"][0]["sha256"] = "f" * 64


def the_takes_reordered(packet: dict) -> None:
    packet["audio"]["rehearsal_takes"].reverse()


@pytest.mark.parametrize("change", [another_take, the_takes_reordered], ids=["takes", "take order"])
async def test_a_draft_differing_in_its_takes_is_not_approved(client, db_session, change):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_clean_draft_approved(client, db_session, project, credential)

    await stored_with(db_session, session, change)

    assert await approved_on_the_tablet(client, credential, session) is None


@pytest.mark.parametrize(
    "change", [another_question, another_finding], ids=["questions", "findings"]
)
async def test_a_draft_differing_only_in_its_check_state_stays_approved(client, db_session, change):
    """Only a change of takes re-opens an approved draft (ADR 0081)."""
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session = await a_clean_draft_approved(client, db_session, project, credential)

    await stored_with(db_session, session, change)

    assert (await approved_on_the_tablet(client, credential, session))["version"] == 1


async def test_a_draft_whose_recorded_nuance_differs_stays_approved(
    client, analyst, speaker, db_session
):
    project, credential = await a_claimed_device(db_session, language_name="Terena")
    session, _parts = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    client.headers.update(team_headers(credential))
    analyst.readings = [{"findings": [ON_FRASE_2]}]
    speaker.line = NAMES_FRASE_2
    await press_terminei(client, session.id, report=await heard_every_part(db_session, session.id))
    await approved(client, credential, session)

    await stored_with(
        db_session, session, lambda packet: packet["check"]["nuances"][0].update(idx="outro")
    )

    assert (await approved_on_the_tablet(client, credential, session))["version"] == 1
