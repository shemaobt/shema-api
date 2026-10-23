"""ENG-1422 — each outside listener is the next number of its version, and every recording is kept.

On the **Checagem externa** of an approved version the team's tablet asks the room for the next
**Outside listener**, sends every **Listener recording** the moment it stops, marks «está boa»
per frase and finishes the listener. Nothing names a person, the bytes are in the bucket before
the row names them, and no recognizer or model ever hears listener audio (the app's ADR 0111).
Two tablets of one team speak through the real doors, one database session per request; the
cases about storage read the rows and the bucket, because that is what they assert.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import outside_listeners as outside_listeners_api
from app.db.models.internalization_room import IRSession
from app.services.internalization_room import hearing
from app.services.internalization_room import outside_listeners as outside_listeners_module
from app.services.internalization_room import questions as question_service
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import capture_segment
from app.services.platform import stt
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.release_harness import (
    CLIP_MS,
    P,
    checked_telling_back,
    desk_passage_release,
    ready_session,
    reported_playback,
    team_release,
    the_one_part_of,
    the_part_recorded_again,
)
from tests.scene_rehearsal_harness import IR, Room, a_room, count, recording
from tests.turn_harness import the_room_agent_is

RETELLING = recording(3, 7)
#: The module, not the function the package re-exports under the same name.
transcriber = importlib.import_module("app.services.translation_helper.transcribe_audio")


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


async def told_in_four_stretches(db: AsyncSession, session) -> BackTranslationState:
    part = await the_one_part_of(db, session)
    quarter = CLIP_MS // 4
    told = [
        await capture_segment(
            db,
            session,
            take_id=part.id,
            starts_ms=index * quarter,
            ends_ms=(index + 1) * quarter,
            bridge_take_id=f"retro-{index}",
            transcript=f"a frase {index + 1} contada de volta",
        )
        for index in range(4)
    ]
    return BackTranslationState(
        scope=session.pericope,
        findings=[],
        checked=True,
        analysed_segment_ids=[stretch.id for stretch in told],
    )


async def nothing_told(_db: AsyncSession, session) -> BackTranslationState:
    return BackTranslationState(scope=session.pericope)


async def approve(room: Room, session_id: str) -> None:
    approved = await room.client.post(team_release(session_id))
    assert approved.status_code == 200, approved.text


async def open_check(room: Room, session_id: str) -> dict[str, Any]:
    opened = await room.client.post(f"{IR}/sessions/{session_id}/external-check/open")
    assert opened.status_code == 200, opened.text
    return dict(opened.json())


async def an_open_check(room: Room, db: AsyncSession, *, tell=None) -> tuple[str, dict[str, Any]]:
    session = await ready_session(db, project_id=TABLET_TEAM, tell=tell)
    await approve(room, session.id)
    return session.id, await open_check(room, session.id)


async def a_second_version(room: Room, db: AsyncSession, session_id: str) -> dict[str, Any]:
    session = await db.get(IRSession, session_id)
    assert session is not None
    await the_part_recorded_again(db, session)
    await reported_playback(db, session, await checked_telling_back(db, session))
    await approve(room, session_id)
    return await open_check(room, session_id)


def at(session_id: str, version: int, rest: str = "") -> str:
    return f"{IR}/sessions/{session_id}/external-check/{version}/listeners{rest}"


async def ask(
    room: Room, session_id: str, version: int, headers: dict[str, str] | None = None
) -> httpx.Response:
    return await room.client.post(at(session_id, version), headers=headers)


async def listener(room: Room, session_id: str, version: int) -> int:
    asked = await ask(room, session_id, version)
    assert asked.status_code == 200, asked.text
    return int(asked.json()["number"])


async def send(
    room: Room,
    session_id: str,
    version: int,
    number: int,
    audio: bytes,
    kind: str,
    *,
    segment_id: str | None = None,
    sha256: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    data = {
        name: value
        for name, value in (("kind", kind), ("segment_id", segment_id), ("sha256", sha256))
        if value is not None
    }
    return await room.client.post(
        at(session_id, version, f"/{number}/recordings"),
        data=data,
        files={"file": ("ouvinte.wav", audio, "audio/wav")},
        headers=headers,
    )


async def sent(
    room: Room,
    session_id: str,
    version: int,
    number: int,
    audio: bytes,
    kind: str,
    segment_id: str | None = None,
) -> dict[str, Any]:
    answered = await send(room, session_id, version, number, audio, kind, segment_id=segment_id)
    assert answered.status_code == 200, answered.text
    return dict(answered.json())


async def mark(
    room: Room,
    session_id: str,
    version: int,
    number: int,
    segment_id: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await room.client.post(
        at(session_id, version, f"/{number}/marks"),
        json={"segment_id": segment_id},
        headers=headers,
    )


async def finish(
    room: Room,
    session_id: str,
    version: int,
    number: int,
    completed: bool,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await room.client.post(
        at(session_id, version, f"/{number}/finish"),
        json={"completed": completed},
        headers=headers,
    )


async def facts(room: Room, session_id: str, version: int, number: int, headers=None):
    return await room.client.get(at(session_id, version, f"/{number}"), headers=headers)


async def read(room: Room, session_id: str, version: int) -> dict[str, Any]:
    answered = await room.client.get(
        f"{IR}/facilitator/sessions/{session_id}/external-check/{version}", headers=room.desk
    )
    assert answered.status_code == 200, answered.text
    return dict(answered.json())


def one_listener(listeners: list[dict[str, Any]], number: int) -> dict[str, Any]:
    (found,) = [each for each in listeners if each["number"] == number]
    return found


async def recordings_of(db: AsyncSession, session_id: str) -> int:
    return await count(db, "ir_external_recordings", "session_id", session_id)


async def test_an_approved_version_with_no_listeners_gives_listener_one(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session)

    asked = await ask(room, session_id, check["version"])

    assert asked.status_code == 200, asked.text
    (listed,) = (await read(room, session_id, 1))["listeners"]
    assert listed["number"] == 1
    assert asked.json() == {
        "number": 1,
        "started_at": listed["started_at"],
        "finished_at": None,
        "completed": False,
        "retold": False,
        "whole": 0,
        "frases": [],
    }


async def test_a_fourth_listener_is_four_and_one_to_three_are_never_given_again(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session)

    numbers = [await listener(room, session_id, check["version"]) for _ in range(4)]

    assert numbers == [1, 2, 3, 4]
    assert [each["number"] for each in (await read(room, session_id, 1))["listeners"]] == [
        1,
        2,
        3,
        4,
    ]


async def test_a_new_version_starts_again_at_one_and_the_old_versions_listeners_stay_readable(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, first = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    await listener(room, session_id, 1)
    kept = await sent(room, session_id, 1, 2, RETELLING, "retell")

    second = await a_second_version(room, db_session, session_id)
    on_two = await listener(room, session_id, second["version"])
    late_on_one = await listener(room, session_id, first["version"])

    assert second["version"] == 2
    assert on_two == 1
    assert late_on_one == 3
    old = await read(room, session_id, 1)
    assert [each["number"] for each in old["listeners"]] == [1, 2, 3]
    assert one_listener(old["listeners"], 2)["retelling"]["recording_id"] == kept["recording_id"]
    assert [each["number"] for each in (await read(room, session_id, 2))["listeners"]] == [1]


async def test_two_tablets_asking_at_once_get_two_different_numbers(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session)

    first, second = await asyncio.gather(
        ask(room, session_id, check["version"]),
        ask(room, session_id, check["version"], headers=room.tablet_b),
    )

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert sorted([first.json()["number"], second.json()["number"]]) == [1, 2]


async def test_a_tablet_that_read_the_last_number_before_the_other_wrote_it_still_gets_the_next_one(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The loser read the last number before the winner committed and meets it at the index.

    Staged by holding the read of the last number still at none, as it answered before the
    winner wrote listener 1; the insert and the unique index that refuses it are real.
    """
    session_id, check = await an_open_check(room, db_session)
    assert await listener(room, session_id, check["version"]) == 1

    the_real_read = outside_listeners_module._last_number
    held = {"still": True}

    async def _before_the_winner(*args: Any, **kwargs: Any) -> int:
        if held.pop("still", False):
            return 0
        return await the_real_read(*args, **kwargs)

    monkeypatch.setattr(outside_listeners_module, "_last_number", _before_the_winner)
    asked = await ask(room, session_id, check["version"])

    assert asked.status_code == 200, asked.text
    assert asked.json()["number"] == 2
    assert [each["number"] for each in (await read(room, session_id, 1))["listeners"]] == [1, 2]


async def test_a_retelling_sent_before_the_tab_closes_is_kept_and_the_listener_reads_started_not_finished(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    await listener(room, session_id, 1)
    fingerprint = hashlib.sha256(RETELLING).hexdigest()

    answered = await send(room, session_id, 1, 2, RETELLING, "retell", sha256=fingerprint)

    assert answered.status_code == 200, answered.text
    kept = answered.json()
    assert kept["recording_id"]
    assert kept["kind"] == "retell"
    assert kept["content_type"] == "audio/wav"
    assert abs(kept["duration_ms"] - 3000) <= 100
    assert kept["size_bytes"] == len(RETELLING)
    assert kept["sha256"] == fingerprint
    assert kept["stored_at"]
    (key,) = [key for key, stored in room.bucket.objects.items() if stored == RETELLING]
    assert key.startswith("internalization-room/external/")
    assert "/2/" in key
    two = one_listener((await read(room, session_id, check["version"]))["listeners"], 2)
    assert two["finished_at"] is None
    assert two["completed"] is False
    assert two["retelling"]["recording_id"] == kept["recording_id"]


async def test_a_frase_only_heard_has_no_entry_and_a_frase_marked_good_with_no_comment_reads_ok(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session, tell=told_in_four_stretches)
    by_number = {frase["frase"]: frase["segment_id"] for frase in check["frases"]}
    assert sorted(by_number) == [1, 2, 3, 4]
    await listener(room, session_id, 1)

    marked = await mark(room, session_id, 1, 1, by_number[4])

    assert marked.status_code == 200, marked.text
    assert marked.json()["frases"] == [
        {"segment_id": by_number[4], "frase": 4, "ok": True, "comments": 0}
    ]
    assert one_listener((await read(room, session_id, 1))["listeners"], 1)["frases"] == [
        {"segment_id": by_number[4], "frase": 4, "ok": True, "comments": []}
    ]


async def test_a_comment_on_a_frase_makes_it_not_ok_before_or_after_the_mark(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session, tell=told_in_four_stretches)
    by_number = {frase["frase"]: frase["segment_id"] for frase in check["frases"]}
    await listener(room, session_id, 1)

    assert (await mark(room, session_id, 1, 1, by_number[2])).status_code == 200
    after_the_mark = await sent(room, session_id, 1, 1, recording(2, 21), "frase", by_number[2])
    before_the_mark = await sent(room, session_id, 1, 1, recording(2, 22), "frase", by_number[1])
    assert (await mark(room, session_id, 1, 1, by_number[1])).status_code == 200

    frases = one_listener((await read(room, session_id, 1))["listeners"], 1)["frases"]
    assert [(frase["frase"], frase["ok"]) for frase in frases] == [(1, False), (2, False)]
    assert [comment["recording_id"] for comment in frases[0]["comments"]] == [
        before_the_mark["recording_id"]
    ]
    assert [comment["recording_id"] for comment in frases[1]["comments"]] == [
        after_the_mark["recording_id"]
    ]


async def test_comments_on_the_whole_passage_are_kept_in_the_order_sent(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)

    first = await sent(room, session_id, 1, 1, recording(2, 31), "whole")
    second = await sent(room, session_id, 1, 1, recording(2, 32), "whole")

    one = one_listener((await read(room, session_id, 1))["listeners"], 1)
    assert [comment["recording_id"] for comment in one["whole"]] == [
        first["recording_id"],
        second["recording_id"],
    ]
    assert one["retelling"] is None


async def test_a_second_retelling_is_the_listeners_retelling_and_the_same_bytes_again_are_the_same_recording(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    first_bytes, second_bytes = recording(2, 41), recording(2, 42)

    first = await sent(room, session_id, 1, 1, first_bytes, "retell")
    again = await sent(room, session_id, 1, 1, first_bytes, "retell")
    held_after_the_resend = list(room.bucket.objects.values()).count(first_bytes)
    rows_after_the_resend = await recordings_of(db_session, session_id)
    second = await sent(room, session_id, 1, 1, second_bytes, "retell")

    assert again["recording_id"] == first["recording_id"]
    assert rows_after_the_resend == 1
    assert held_after_the_resend == 1
    one = one_listener((await read(room, session_id, 1))["listeners"], 1)
    assert one["retelling"]["recording_id"] == second["recording_id"]
    assert first_bytes in room.bucket.objects.values()


async def test_finishing_now_keeps_everything_and_reads_not_complete_and_finishing_whole_reads_complete(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    await listener(room, session_id, 1)
    kept = await sent(room, session_id, 1, 1, RETELLING, "retell")

    now = await finish(room, session_id, 1, 1, completed=False)
    whole = await finish(room, session_id, 1, 2, completed=True)

    assert (now.status_code, whole.status_code) == (200, 200), (now.text, whole.text)
    listeners = (await read(room, session_id, 1))["listeners"]
    one, two = one_listener(listeners, 1), one_listener(listeners, 2)
    assert one["finished_at"] is not None
    assert one["completed"] is False
    assert one["retelling"]["recording_id"] == kept["recording_id"]
    assert two["finished_at"] is not None
    assert two["completed"] is True


async def test_a_second_finish_keeps_how_the_listener_first_ended(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    first = await finish(room, session_id, 1, 1, completed=False)

    second = await finish(room, session_id, 1, 1, completed=True)

    assert second.status_code == 200, second.text
    assert second.json()["completed"] is False
    assert second.json()["finished_at"] == first.json()["finished_at"]
    one = one_listener((await read(room, session_id, 1))["listeners"], 1)
    assert (one["completed"], one["finished_at"]) == (False, first.json()["finished_at"])


async def test_the_bytes_are_in_the_bucket_before_the_recording_is_attached(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)

    async def _the_bucket_is_down(*_: Any, **__: Any) -> None:
        raise ConnectionError("o balde caiu")

    monkeypatch.setattr(room.bucket, "put", _the_bucket_is_down)
    with pytest.raises(ConnectionError):
        await send(room, session_id, 1, 1, RETELLING, "retell")

    assert one_listener((await read(room, session_id, 1))["listeners"], 1)["retelling"] is None
    assert await recordings_of(db_session, session_id) == 0


@pytest.mark.parametrize(
    ("kind", "names", "audio", "sha256", "status", "code"),
    [
        ("frase", None, RETELLING, None, 400, None),
        ("frase", "nenhuma", RETELLING, None, 400, None),
        ("retell", "the first", RETELLING, None, 400, None),
        ("song", None, RETELLING, None, 400, None),
        ("retell", None, b"", None, 400, None),
        ("retell", None, RETELLING, "0" * 64, 422, "TAKE_FINGERPRINT_DIFFERS"),
    ],
    ids=["frase-sem-frase", "frase-alheia", "reconto-com-frase", "tipo-alheio", "vazio", "sha"],
)
async def test_a_recording_names_a_frase_of_its_version_or_is_refused(
    room: Room,
    db_session: AsyncSession,
    kind: str,
    names: str | None,
    audio: bytes,
    sha256: str | None,
    status: int,
    code: str | None,
) -> None:
    session_id, check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    segment_id = check["frases"][0]["segment_id"] if names == "the first" else names
    held = dict(room.bucket.objects)

    refused = await send(room, session_id, 1, 1, audio, kind, segment_id=segment_id, sha256=sha256)

    assert refused.status_code == status, refused.text
    if code is not None:
        assert refused.json()["code"] == code
    assert room.bucket.objects == held
    assert await recordings_of(db_session, session_id) == 0


async def test_a_check_of_a_forced_version_with_nothing_told_takes_comments_per_part(
    room: Room, db_session: AsyncSession
) -> None:
    session = await ready_session(db_session, project_id=TABLET_TEAM, tell=nothing_told)
    forced = await room.client.post(
        desk_passage_release(TABLET_TEAM, P), headers=room.desk, json={"force": True}
    )
    assert forced.status_code == 200, forced.text
    check = await open_check(room, session.id)
    assert check["frases"] == []
    await listener(room, session.id, 1)

    on_the_part = await send(
        room, session.id, 1, 1, RETELLING, "frase", segment_id=check["takes"][0]["take_id"]
    )
    on_nothing = await send(
        room, session.id, 1, 1, recording(2, 51), "frase", segment_id=str(uuid.uuid4())
    )

    assert on_the_part.status_code == 200, on_the_part.text
    assert on_nothing.status_code == 400, on_nothing.text
    assert recording(2, 51) not in room.bucket.objects.values()
    assert await recordings_of(db_session, session.id) == 1


async def test_an_unknown_listener_or_a_version_never_opened_is_not_found(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)

    no_listener = await send(room, session_id, 1, 7, RETELLING, "retell")
    no_check = await ask(room, session_id, 9)

    assert no_listener.status_code == 404, no_listener.text
    assert no_check.status_code == 404, no_check.text
    assert await recordings_of(db_session, session_id) == 0


async def test_another_teams_tablet_reaches_nothing_of_this_teams_check(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    stranger = (await a_linked_tablet(db_session, team_id=f"outra-{uuid.uuid4().hex[:6]}")).headers
    segment_id = check["frases"][0]["segment_id"]

    answers = [
        await ask(room, session_id, 1, headers=stranger),
        await send(room, session_id, 1, 1, RETELLING, "retell", headers=stranger),
        await mark(room, session_id, 1, 1, segment_id, headers=stranger),
        await finish(room, session_id, 1, 1, completed=True, headers=stranger),
        await facts(room, session_id, 1, 1, headers=stranger),
    ]

    assert [answer.status_code for answer in answers] == [404] * 5
    (one,) = (await read(room, session_id, 1))["listeners"]
    assert (one["retelling"], one["frases"], one["finished_at"]) == (None, [], None)
    assert await recordings_of(db_session, session_id) == 0


async def test_no_transcriber_and_no_model_hears_a_listener_recording(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, check = await an_open_check(room, db_session)
    called: list[str] = []

    def _recorder(name: str):
        async def _called(*_: Any, **__: Any) -> Any:
            called.append(name)
            raise AssertionError(f"{name} ouviu um ouvinte")

        return _called

    for owner, name in (
        (hearing, "transcribe_audio_detailed"),
        (transcriber, "transcribe_audio"),
        (transcriber, "transcribe_audio_detailed"),
        (stt, "transcribe_speech"),
        (question_service, "transcribe_speech"),
    ):
        monkeypatch.setattr(owner, name, _recorder(f"{owner.__name__}.{name}"))
    the_room_agent_is(
        monkeypatch,
        turn=_recorder("turn"),
        analyst=_recorder("analyst"),
        classifier=_recorder("classifier"),
        judge=_recorder("judge"),
    )
    segment_id = check["frases"][0]["segment_id"]

    number = await listener(room, session_id, 1)
    await sent(room, session_id, 1, number, recording(2, 61), "retell")
    await sent(room, session_id, 1, number, recording(2, 62), "whole")
    await sent(room, session_id, 1, number, recording(2, 63), "whole")
    await sent(room, session_id, 1, number, recording(2, 64), "frase", segment_id)
    assert (await mark(room, session_id, 1, number, segment_id)).status_code == 200
    assert (await finish(room, session_id, 1, number, completed=True)).status_code == 200
    assert (await facts(room, session_id, 1, number)).status_code == 200
    await read(room, session_id, 1)
    assert (await room.client.get(f"{IR}/sessions/{session_id}")).status_code == 200

    assert called == []
    assert room.heard == []


async def test_the_session_read_counts_this_versions_listeners(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    await listener(room, session_id, 1)

    on_one = await room.client.get(f"{IR}/sessions/{session_id}")
    await a_second_version(room, db_session, session_id)
    on_two = await room.client.get(f"{IR}/sessions/{session_id}")

    assert on_one.json()["approved"]["listeners"] == 2
    assert on_two.json()["approved"]["version"] == 2
    assert on_two.json()["approved"]["listeners"] == 0


async def test_a_zerar_keeps_the_listeners_and_their_recordings_under_the_passages_archive(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session)
    segment_id = check["frases"][0]["segment_id"]
    await listener(room, session_id, 1)
    kept = await sent(room, session_id, 1, 1, RETELLING, "retell")
    assert (await mark(room, session_id, 1, 1, segment_id)).status_code == 200

    zerado = await room.client.post(
        f"{IR}/facilitator/projects/{TABLET_TEAM}/passages/{P}/archive", headers=room.desk
    )
    after = await ask(room, session_id, 1)

    assert zerado.status_code == 200, zerado.text
    archive_id = zerado.json()["archive"]["id"]
    for table in ("ir_external_listeners", "ir_external_recordings", "ir_external_marks"):
        stamped = await db_session.execute(
            text(f"SELECT archive_id FROM {table} WHERE session_id = :v"), {"v": session_id}
        )
        assert list(stamped.scalars()) == [archive_id], table
    (one,) = (await read(room, session_id, 1))["listeners"]
    assert one["retelling"]["recording_id"] == kept["recording_id"]
    assert [frase["ok"] for frase in one["frases"]] == [True]
    assert after.status_code == 404, after.text


async def test_the_team_reads_a_listeners_facts_and_never_their_audio(
    room: Room, db_session: AsyncSession
) -> None:
    session_id, check = await an_open_check(room, db_session, tell=told_in_four_stretches)
    by_number = {frase["frase"]: frase["segment_id"] for frase in check["frases"]}
    await listener(room, session_id, 1)
    await sent(room, session_id, 1, 1, recording(2, 71), "retell")
    await sent(room, session_id, 1, 1, recording(2, 72), "whole")
    await sent(room, session_id, 1, 1, recording(2, 73), "whole")
    await sent(room, session_id, 1, 1, recording(2, 74), "frase", by_number[3])
    await mark(room, session_id, 1, 1, by_number[1])

    answered = await facts(room, session_id, 1, 1, headers=room.tablet_b)

    assert answered.status_code == 200, answered.text
    body = answered.json()
    started_at = one_listener((await read(room, session_id, 1))["listeners"], 1)["started_at"]
    assert body == {
        "number": 1,
        "started_at": started_at,
        "finished_at": None,
        "completed": False,
        "retold": True,
        "whole": 2,
        "frases": [
            {"segment_id": by_number[1], "frase": 1, "ok": True, "comments": 0},
            {"segment_id": by_number[3], "frase": 3, "ok": False, "comments": 1},
        ],
    }


async def test_a_finish_that_lands_while_another_is_written_keeps_the_first_ending(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second finish read the listener unfinished, and the first finish commits before it
    writes.

    Staged by sending «terminar agora» from the other tablet as the second finish's read of the
    listener returns; the read, both writes and the answers are real.
    """
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    the_real_read = outside_listeners_api.the_listener
    held = {"still": True}
    first: list[httpx.Response] = []

    async def _read_and_then_the_other_finish_lands(*args: Any, **kwargs: Any):
        read = await the_real_read(*args, **kwargs)
        if held.pop("still", False):
            first.append(
                await finish(room, session_id, 1, 1, completed=False, headers=room.tablet_b)
            )
        return read

    monkeypatch.setattr(
        outside_listeners_api, "the_listener", _read_and_then_the_other_finish_lands
    )
    second = await finish(room, session_id, 1, 1, completed=True)

    assert second.status_code == 200, second.text
    ending = (first[0].json()["completed"], first[0].json()["finished_at"])
    assert ending[0] is False
    assert (second.json()["completed"], second.json()["finished_at"]) == ending
    one = one_listener((await read(room, session_id, 1))["listeners"], 1)
    assert (one["completed"], one["finished_at"]) == ending


async def test_a_recording_that_lands_while_the_passage_is_zerada_carries_the_archive_stamp(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    the_real_put = room.bucket.put
    archived: list[str] = []

    async def _zerada_while_uploading(key: str, data: bytes, content_type: str) -> None:
        zerado = await room.client.post(
            f"{IR}/facilitator/projects/{TABLET_TEAM}/passages/{P}/archive", headers=room.desk
        )
        archived.append(zerado.json()["archive"]["id"])
        await the_real_put(key, data, content_type)

    monkeypatch.setattr(room.bucket, "put", _zerada_while_uploading)
    sent_during = await send(room, session_id, 1, 1, RETELLING, "retell")

    assert sent_during.status_code == 200, sent_during.text
    stamped = await db_session.execute(
        text("SELECT archive_id FROM ir_external_recordings WHERE session_id = :v"),
        {"v": session_id},
    )
    assert list(stamped.scalars()) == archived


def a_zerar_lands_once_the_check_is_read(room: Room, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Staged as the door's read of the check returns, through the Desk's own request; the
    read and the write after it are real."""
    the_real_read = outside_listeners_api.the_check_of_version
    archived: list[str] = []

    async def _read_and_then_the_zerar_lands(*args: Any, **kwargs: Any):
        read = await the_real_read(*args, **kwargs)
        if not archived:
            zerado = await room.client.post(
                f"{IR}/facilitator/projects/{TABLET_TEAM}/passages/{P}/archive", headers=room.desk
            )
            archived.append(zerado.json()["archive"]["id"])
        return read

    monkeypatch.setattr(
        outside_listeners_api, "the_check_of_version", _read_and_then_the_zerar_lands
    )
    return archived


async def stamps_of(db: AsyncSession, table: str, session_id: str) -> list[str | None]:
    stamped = await db.execute(
        text(f"SELECT archive_id FROM {table} WHERE session_id = :v"), {"v": session_id}
    )
    return list(stamped.scalars())


async def test_a_listener_asked_for_while_the_passage_is_zerada_carries_the_archive_stamp(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, _check = await an_open_check(room, db_session)
    archived = a_zerar_lands_once_the_check_is_read(room, monkeypatch)

    await ask(room, session_id, 1)

    assert archived
    assert await stamps_of(db_session, "ir_external_listeners", session_id) == archived


async def test_a_mark_made_while_the_passage_is_zerada_carries_the_archive_stamp(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, check = await an_open_check(room, db_session)
    await listener(room, session_id, 1)
    archived = a_zerar_lands_once_the_check_is_read(room, monkeypatch)

    await mark(room, session_id, 1, 1, check["frases"][0]["segment_id"])

    assert archived
    assert await stamps_of(db_session, "ir_external_marks", session_id) == archived
