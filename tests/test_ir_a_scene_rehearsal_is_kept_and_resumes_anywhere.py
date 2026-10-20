"""ENG-1312 — a scene rehearsal is kept on the server and resumes on any tablet of the team.

The team records a whole scene in its mother tongue and translates it frase by frase. The
server keeps one record per **Scene rehearsal**: the recording, never heard by the recognizer,
the **Scene frases** with their places, the sent stamp and the team's scene label apart from
the classifier's guess. Two tablets of one team speak through the real doors. The cases that
say a row, a stamp or an object exists read the tables and the bucket, because that is what
they assert.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.sessions import create_session
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import a_session
from tests.opening_harness import a_scripted_room, the_tablet_opens
from tests.scene_rehearsal_harness import (
    IR,
    SAID,
    SCENE,
    P,
    Room,
    a_room,
    count,
    frases_read_by_b,
    key_of,
    read_by_b,
    record,
    recorded,
    recording,
    restart,
    sent,
    translate,
    translated,
    write,
)


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


def current(frases: list[dict[str, Any]]) -> list[tuple[int, int]]:
    return [(f["starts_ms"], f["ends_ms"]) for f in frases if f["replaced_by"] is None]


async def zerar(room: Room) -> str:
    zerado = await room.client.post(
        f"{IR}/facilitator/projects/{TABLET_TEAM}/passages/{P}/archive", headers=room.desk
    )
    assert zerado.status_code == 200, zerado.text
    return str(zerado.json()["archive"]["id"])


async def stamps(db: AsyncSession, table: str, column: str, value: str) -> list[str | None]:
    found = await db.execute(
        text(f"SELECT archive_id FROM {table} WHERE {column} = :v"), {"v": value}
    )
    return list(found.scalars())


async def test_a_40_second_scene_recording_is_kept_for_its_session_and_scene_and_never_reaches_the_recognizer(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    kept = await record(room, session_id)

    assert kept.status_code == 200, kept.text
    body = kept.json()
    assert body["session_id"] == session_id
    assert body["pericope"] == P
    assert abs(body["duration_ms"] - 40_000) <= 50
    assert await count(db_session, "ir_scene_rehearsals", "session_id", session_id) == 1
    assert SCENE in room.bucket.objects.values()
    assert room.heard == []
    assert await count(db_session, "ir_turns", "session_id", session_id) == 0


async def test_an_unsent_rehearsal_opened_on_another_tablet_resumes_after_frase_3(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000), (11000, 17000)])

    (rehearsal,) = await read_by_b(room, session_id)

    assert rehearsal["rehearsal_id"] == rehearsal_id
    assert rehearsal["sent_at"] is None
    assert current(rehearsal["frases"]) == [(0, 5000), (5000, 11000), (11000, 17000)]
    heard_on_b = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio",
        headers=room.tablet_b,
    )
    assert heard_on_b.status_code == 307, heard_on_b.text
    assert room.signed == [key_of(room, SCENE)]


async def test_a_last_frase_replaced_on_one_tablet_is_the_one_the_other_tablet_reads(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    *_, third = await translated(
        room, session_id, rehearsal_id, [(0, 5000), (5000, 11000), (11000, 17000)]
    )

    moved = await translate(
        room, session_id, rehearsal_id, (11000, 18500), recording(1, 900), replaces=third
    )

    assert moved.status_code == 200, moved.text
    frases = await frases_read_by_b(room, session_id)
    assert current(frases) == [(0, 5000), (5000, 11000), (11000, 18500)]
    replacing = next(f["frase_id"] for f in frases if f["ends_ms"] == 18500)
    assert {f["frase_id"]: f["replaced_by"] for f in frases}[third] == replacing


@pytest.mark.parametrize(
    ("place", "code"),
    [
        pytest.param((None, 5000), None, id="no starts_ms"),
        pytest.param((5000, 5000), "FRASE_OUT_OF_PLACE", id="ends_ms not after starts_ms"),
        pytest.param((30000, 41000), "FRASE_OUT_OF_PLACE", id="ends_ms beyond the recording"),
    ],
)
async def test_a_frase_with_no_place_in_the_recording_is_refused_and_the_record_keeps_no_frase(
    room: Room,
    db_session: AsyncSession,
    place: tuple[int | None, int | None],
    code: str | None,
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    refused = await translate(room, session_id, rehearsal_id, place, recording(1, 100))

    assert refused.status_code == 422, refused.text
    assert refused.json().get("code") == code
    assert await frases_read_by_b(room, session_id) == []


async def test_a_zerar_stamps_the_passages_scene_rehearsals_and_their_frases(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_scripted_room(monkeypatch)
    session_id = await a_session(db_session, language="pt")
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])

    archive_id = await zerar(room)

    opened = await the_tablet_opens(room.client, room.credential, {"pericope": P, "language": "pt"})
    assert opened["session_id"] != session_id
    assert await read_by_b(room, opened["session_id"]) == []
    assert await stamps(db_session, "ir_scene_rehearsals", "id", rehearsal_id) == [archive_id]
    assert await stamps(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == [
        archive_id,
        archive_id,
    ]


async def test_a_rehearsal_recorded_for_scene_2_keeps_scene_2_as_the_teams_label_said_at_the_recording(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    await write(db_session, "scene_guess", "S3", rehearsal_id)

    (on_the_tablet,) = await read_by_b(room, session_id)
    assert (on_the_tablet["scene"], on_the_tablet["scene_said"]) == ("S2", "recording")
    assert "S3" not in str(on_the_tablet)


async def test_a_scene_that_is_not_one_of_the_passages_is_kept_as_unknown_not_as_none(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    foreign = await record(room, session_id, scene="S99")
    unmarked = await record(room, session_id, audio=recording(40, 2), scene=None)

    assert foreign.status_code == 200, foreign.text
    assert unmarked.status_code == 200, unmarked.text
    assert (foreign.json()["scene"], foreign.json()["scene_said"]) == (None, "recording"), (
        "um rótulo que a passagem não tem era devolvido como se a equipe não tivesse marcado nada"
    )
    assert (unmarked.json()["scene"], unmarked.json()["scene_said"]) == (None, None)


async def test_the_label_the_passage_lacks_is_remembered_as_sent_beside_the_scene_it_is_not(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    foreign = await record(room, session_id, scene="S99")
    labelled = await record(room, session_id, audio=recording(40, 2), scene="S2")

    remembered = {}
    for kept in (foreign, labelled):
        row = await db_session.execute(
            text("SELECT scene, scene_foreign FROM ir_scene_rehearsals WHERE id = :id"),
            {"id": kept.json()["rehearsal_id"]},
        )
        remembered[kept.json()["rehearsal_id"]] = tuple(row.one())
    assert remembered[foreign.json()["rehearsal_id"]] == (None, "S99"), (
        "o rótulo que a passagem não tem não era guardado como a tablet o mandou"
    )
    assert remembered[labelled.json()["rehearsal_id"]] == ("S2", None)


async def test_a_second_session_of_the_passage_lists_its_live_scene_rehearsals_before_any_turn(
    room: Room, db_session: AsyncSession
) -> None:
    portuguese = await a_session(db_session, language="pt")
    rehearsal_id = await recorded(room, portuguese)
    english = await a_session(db_session, language="en")

    listed = await read_by_b(room, english)

    assert [(r["rehearsal_id"], r["session_id"], r["n"]) for r in listed] == [
        (rehearsal_id, portuguese, 1)
    ]


async def test_the_same_scene_recording_sent_twice_is_one_rehearsal(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    first = (await record(room, session_id)).json()

    again = await record(room, session_id)

    assert again.status_code == 200, again.text
    assert (again.json()["rehearsal_id"], again.json()["n"]) == (first["rehearsal_id"], first["n"])
    assert await count(db_session, "ir_scene_rehearsals", "session_id", session_id) == 1


async def test_the_same_frase_sent_twice_is_one_frase(room: Room, db_session: AsyncSession) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    frase = recording(1, 100)
    assert (await translate(room, session_id, rehearsal_id, (0, 5000), frase)).status_code == 200

    again = await translate(room, session_id, rehearsal_id, (0, 5000), frase)

    assert again.status_code == 200, again.text
    assert current(await frases_read_by_b(room, session_id)) == [(0, 5000)]
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 1


async def test_a_frase_with_no_words_is_refused_and_becomes_no_frase(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id = await recorded(room, session_id)
    frase = recording(1, 100)
    room.answers.append("")

    refused = await translate(room, session_id, rehearsal_id, (0, 5000), frase)

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "WORDLESS_TELLING"
    assert await frases_read_by_b(room, session_id) == []
    assert frase in room.bucket.objects.values()
    assert [call.get("language") for call in room.heard] == ["pt"]


@pytest.mark.parametrize("lang", ["pt", "en"])
async def test_a_frase_is_heard_in_the_sessions_language(
    room: Room, db_session: AsyncSession, lang: str
) -> None:
    session_id = await a_session(db_session, language=lang)
    rehearsal_id = await recorded(room, session_id)

    kept = await translate(room, session_id, rehearsal_id, (0, 5000), recording(1, 100))

    assert kept.status_code == 200, kept.text
    assert [call.get("language") for call in room.heard] == [lang]


async def test_a_frase_translated_again_keeps_the_earlier_one_and_its_audio_as_history(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    places = [(0, 4000), (4000, 9000), (9000, 13000), (13000, 17000)]
    *_, third, _fourth = await translated(room, session_id, rehearsal_id, places)
    earlier_bytes = recording(1, 102)
    assert earlier_bytes in room.bucket.objects.values()

    again = await translate(
        room, session_id, rehearsal_id, (9000, 13000), recording(1, 950), replaces=third
    )

    assert again.status_code == 200, again.text
    frases = await frases_read_by_b(room, session_id)
    assert current(frases) == places
    replacing = next(
        f["frase_id"] for f in frases if f["replaced_by"] is None and f["starts_ms"] == 9000
    )
    assert {f["frase_id"]: f["replaced_by"] for f in frases}[third] == replacing
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 5
    assert earlier_bytes in room.bucket.objects.values()


async def test_a_sent_rehearsal_takes_no_frase_and_is_still_heard(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await sent(db_session, rehearsal_id)

    frase = await translate(room, session_id, rehearsal_id, (0, 5000), recording(1, 100))

    assert frase.status_code == 409, frase.text
    assert frase.json()["code"] == "SCENE_REHEARSAL_SENT"
    (listed,) = await read_by_b(room, session_id)
    assert listed["rehearsal_id"] == rehearsal_id
    assert listed["sent_at"] is not None
    heard = await room.client.get(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/audio"
    )
    assert heard.status_code == 307, heard.text


async def test_a_frase_may_not_replace_another_rehearsals_frase(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    other_id = await recorded(room, session_id, recording(10, 2))
    kept = await translate(room, session_id, other_id, (0, 5000), recording(1, 500))
    assert kept.status_code == 200, kept.text
    (other,) = [
        f["frase_id"]
        for r in await read_by_b(room, session_id)
        if r["rehearsal_id"] == other_id
        for f in r["frases"]
    ]
    before = await read_by_b(room, session_id)

    refused = await translate(
        room, session_id, rehearsal_id, (0, 7000), recording(1, 901), replaces=other
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "UNKNOWN_REFERENCE"
    assert await read_by_b(room, session_id) == before


async def test_a_frase_translated_again_offline_twice_over_its_own_place_lands_at_the_newest(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    (first,) = await translated(room, session_id, rehearsal_id, [(0, 5000)], tone=300)
    again = await translate(
        room, session_id, rehearsal_id, (0, 5000), recording(1, 900), replaces=first
    )
    assert again.status_code == 200, again.text
    second = next(f["frase_id"] for f in again.json()["frases"] if f["replaced_by"] is None)

    third = await translate(
        room, session_id, rehearsal_id, (0, 5000), recording(1, 901), replaces=first
    )

    assert third.status_code == 200, third.text
    frases = await frases_read_by_b(room, session_id)
    assert current(frases) == [(0, 5000)]
    newest = next(f for f in frases if f["replaced_by"] is None)
    assert newest["replaces"] == second
    assert {f["frase_id"]: f["replaced_by"] for f in frases}[second] == newest["frase_id"]


async def test_a_panorama_session_keeps_no_scene_rehearsal(
    room: Room, db_session: AsyncSession
) -> None:
    panorama = await create_session(
        db_session, project_id=TABLET_TEAM, pericope="OV-Ruth", language="pt"
    )

    kept = await record(room, panorama.id, scene=None)
    listed = await room.client.get(f"{IR}/sessions/{panorama.id}/scene-rehearsals")

    assert kept.status_code == 400, kept.text
    assert kept.json()["code"] == "PANORAMA_RECORDS_NOTHING"
    assert listed.status_code == 400, listed.text
    assert room.bucket.objects == {}


async def test_a_scene_rehearsal_that_lands_after_a_zerar_is_not_listed_for_the_next_session(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await zerar(room)
    await write(db_session, "archive_id", None, rehearsal_id)
    fresh = await create_session(db_session, pericope=P, project_id=TABLET_TEAM)

    assert await read_by_b(room, fresh.id) == []


async def test_a_frase_heard_while_the_rehearsal_is_sent_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    async def send() -> None:
        await sent(db_session, rehearsal_id)

    room.while_hearing.append(send)
    late = await translate(room, session_id, rehearsal_id, (0, 5000), recording(1, 700))

    assert late.status_code == 409, late.text
    assert late.json()["code"] == "SCENE_REHEARSAL_SENT"
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 0


async def test_a_frase_heard_while_the_passage_is_zerada_carries_the_archive_stamp(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    archived: list[str] = []

    async def zera() -> None:
        archived.append(await zerar(room))

    room.while_hearing.append(zera)
    await translate(room, session_id, rehearsal_id, (0, 5000), recording(1, 700))

    assert await stamps(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == archived


async def restarted(room: Room, session_id: str, rehearsal_id: str) -> str:
    answered = await restart(room, session_id, rehearsal_id)
    assert answered.status_code == 200, answered.text
    return str(answered.json()["after_restart"])


async def snapshots(db: AsyncSession, rehearsal_id: str) -> list[dict[str, Any]]:
    found = await db.execute(
        text("SELECT snapshot FROM ir_scene_restarts WHERE rehearsal_id = :r ORDER BY n"),
        {"r": rehearsal_id},
    )
    return [json.loads(row) if isinstance(row, str) else row for row in found.scalars()]


async def test_recomecar_after_two_frases_archives_them_with_the_record_as_it_was(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    two = await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])
    attempt = str(uuid.uuid4())

    answered = await restart(room, session_id, rehearsal_id, attempt)

    assert answered.status_code == 200, answered.text
    (rehearsal,) = await read_by_b(room, session_id)
    assert rehearsal["frases"] == []
    assert rehearsal["after_restart"] == attempt
    assert (rehearsal["rehearsal_id"], rehearsal["n"]) == (rehearsal_id, 1)
    assert abs(rehearsal["duration_ms"] - 40_000) <= 50
    (snapshot,) = await snapshots(db_session, rehearsal_id)
    assert [f["frase_id"] for f in snapshot["frases"]] == two
    assert await count(db_session, "ir_scene_frases", "restart_id", attempt) == 2
    kept = list(room.bucket.objects.values())
    assert recording(1, 100) in kept and recording(1, 101) in kept
    assert SCENE in kept


async def test_the_same_restart_sent_twice_is_one_restart(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    attempt = str(uuid.uuid4())
    first = await restart(room, session_id, rehearsal_id, attempt)
    assert first.status_code == 200, first.text
    kept = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 800), after_restart=attempt
    )
    assert kept.status_code == 200, kept.text

    again = await restart(room, session_id, rehearsal_id, attempt)

    assert again.status_code == 200, again.text
    assert again.json()["after_restart"] == attempt
    assert await count(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == 1
    assert current(await frases_read_by_b(room, session_id)) == [(0, 4000)]


async def test_a_frase_recorded_before_a_restart_and_sent_after_it_is_set_aside(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    after = await restarted(room, session_id, rehearsal_id)

    late = await translate(room, session_id, rehearsal_id, (5000, 11000), recording(1, 600))
    fresh = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 601), after_restart=after
    )

    assert late.status_code == 200, late.text
    assert fresh.status_code == 200, fresh.text
    assert current(await frases_read_by_b(room, session_id)) == [(0, 4000)]
    assert await count(db_session, "ir_scene_frases", "restart_id", after) == 2


async def test_a_frase_heard_while_the_translation_restarts_is_set_aside_with_the_ones_before_it(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    attempts: list[str] = []

    async def recomeca() -> None:
        attempts.append(await restarted(room, session_id, rehearsal_id))

    room.while_hearing.append(recomeca)
    late = await translate(room, session_id, rehearsal_id, (5000, 11000), recording(1, 700))

    assert late.status_code == 200, late.text
    assert await frases_read_by_b(room, session_id) == []
    assert await count(db_session, "ir_scene_frases", "restart_id", attempts[0]) == 2


async def test_a_frase_of_an_offline_restart_waits_for_that_restart_and_then_counts(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    attempt = str(uuid.uuid4())

    early = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=attempt
    )

    assert early.status_code == 200, early.text
    assert current(await frases_read_by_b(room, session_id)) == [(0, 5000)]

    landed = await restart(room, session_id, rehearsal_id, attempt)

    assert landed.status_code == 200, landed.text
    assert current(await frases_read_by_b(room, session_id)) == [(0, 4000)]
    (snapshot,) = await snapshots(db_session, rehearsal_id)
    assert [(f["starts_ms"], f["ends_ms"]) for f in snapshot["frases"]] == [(0, 5000)]


async def test_a_sent_rehearsal_takes_no_restart(room: Room, db_session: AsyncSession) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await sent(db_session, rehearsal_id)

    refused = await restart(room, session_id, rehearsal_id)

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "SCENE_REHEARSAL_SENT"
    assert await count(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == 0


async def test_a_zerar_stamps_the_scene_rehearsals_restarts(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])
    await restarted(room, session_id, rehearsal_id)

    archive_id = await zerar(room)

    assert await stamps(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == [
        archive_id
    ]
    assert await stamps(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == [
        archive_id,
        archive_id,
    ]


async def test_a_restart_that_lands_as_the_passage_is_zerada_carries_the_archive_stamp(
    room: Room, db_session: AsyncSession
) -> None:
    from app.db.models.internalization_room import IRSceneRehearsal
    from app.services.internalization_room.scene_rehearsals import restart_the_scene_translation

    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    rehearsal = await db_session.get(IRSceneRehearsal, rehearsal_id)
    assert rehearsal is not None
    archive_id = await zerar(room)

    await restart_the_scene_translation(
        db_session, rehearsal, attempt=str(uuid.uuid4()), closes=None
    )

    assert await stamps(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == [
        archive_id
    ]


async def test_two_restarts_sent_in_order_leave_the_second_attempt_current(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    x, y = str(uuid.uuid4()), str(uuid.uuid4())

    assert (await restart(room, session_id, rehearsal_id, x)).status_code == 200
    fx = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=x
    )
    assert (await restart(room, session_id, rehearsal_id, y, closes=x)).status_code == 200
    fy = await translate(
        room, session_id, rehearsal_id, (0, 6000), recording(1, 601), after_restart=y
    )

    assert (fx.status_code, fy.status_code) == (200, 200)
    (rehearsal,) = await read_by_b(room, session_id)
    assert rehearsal["after_restart"] == y
    assert current(rehearsal["frases"]) == [(0, 6000)]


async def test_a_restart_that_lands_before_the_one_it_closes_waits_for_it(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    x, y = str(uuid.uuid4()), str(uuid.uuid4())

    early = await restart(room, session_id, rehearsal_id, y, closes=x)
    fy = await translate(
        room, session_id, rehearsal_id, (0, 6000), recording(1, 601), after_restart=y
    )
    assert (await restart(room, session_id, rehearsal_id, x)).status_code == 200
    fx = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=x
    )
    retried = await restart(room, session_id, rehearsal_id, y, closes=x)

    assert early.status_code == 409, early.text
    assert early.json()["code"] == "RESTART_OUT_OF_ORDER"
    assert (fy.status_code, fx.status_code, retried.status_code) == (200, 200, 200)
    (rehearsal,) = await read_by_b(room, session_id)
    assert rehearsal["after_restart"] == y
    assert current(rehearsal["frases"]) == [(0, 6000)]


async def test_a_frase_naming_another_scene_rehearsals_restart_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    sibling_id = await recorded(room, session_id, recording(10, 2))
    theirs = await restarted(room, session_id, sibling_id)

    refused = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=theirs
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "UNKNOWN_REFERENCE"
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 0


async def test_an_earlier_restart_resent_after_a_later_one_landed_changes_nothing(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    x, y = str(uuid.uuid4()), str(uuid.uuid4())
    assert (await restart(room, session_id, rehearsal_id, x)).status_code == 200
    assert (await restart(room, session_id, rehearsal_id, y, closes=x)).status_code == 200
    fy = await translate(
        room, session_id, rehearsal_id, (0, 6000), recording(1, 601), after_restart=y
    )
    assert fy.status_code == 200, fy.text

    again = await restart(room, session_id, rehearsal_id, x)

    assert again.status_code == 200, again.text
    (rehearsal,) = await read_by_b(room, session_id)
    assert rehearsal["after_restart"] == y
    assert current(rehearsal["frases"]) == [(0, 6000)]
    assert await count(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == 2


async def test_a_restart_whose_attempt_is_another_scene_rehearsals_restart_is_refused(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    sibling_id = await recorded(room, session_id, recording(10, 2))
    theirs = await restarted(room, session_id, sibling_id)

    refused = await restart(room, session_id, rehearsal_id, theirs)

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "UNKNOWN_REFERENCE"
    assert await count(db_session, "ir_scene_restarts", "rehearsal_id", rehearsal_id) == 0


async def read_by_the_reader(room: Room, session_id: str) -> list[dict[str, Any]]:
    listed = await room.client.get(
        f"{IR}/facilitator/sessions/{session_id}/scene-rehearsals", headers=room.desk
    )
    assert listed.status_code == 200, listed.text
    return list(listed.json()["scene_rehearsals"])


async def test_the_reader_opens_a_zerada_sessions_scene_rehearsal_with_its_restart_and_its_words(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    two = await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])
    await restarted(room, session_id, rehearsal_id)
    archive_id = await zerar(room)

    (read,) = await read_by_the_reader(room, session_id)

    assert read["rehearsal_id"] == rehearsal_id
    assert read["archive_id"] == archive_id
    (restart_read,) = read["restarts"]
    assert restart_read["restarted_at"]
    assert [(f["frase_id"], f["transcript"]) for f in restart_read["snapshot"]["frases"]] == [
        (two[0], SAID),
        (two[1], SAID),
    ]


async def test_the_reader_reads_the_current_frases_words(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    room.answers.extend(["a primeira frase", "a segunda frase"])
    await translated(room, session_id, rehearsal_id, [(0, 5000), (5000, 11000)])

    (read,) = await read_by_the_reader(room, session_id)

    assert [(f["starts_ms"], f["transcript"]) for f in read["frases"]] == [
        (0, "a primeira frase"),
        (5000, "a segunda frase"),
    ]


async def test_the_reader_shows_the_classifiers_guess_beside_the_teams_label(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)

    (read,) = await read_by_the_reader(room, session_id)
    assert (read["scene"], read["scene_said"], read["scene_guess"]) == ("S2", "recording", None)

    await write(db_session, "scene_guess", "S3", rehearsal_id)

    (read,) = await read_by_the_reader(room, session_id)
    assert (read["scene"], read["scene_guess"]) == ("S2", "S3")


async def test_a_second_tablet_and_the_reader_both_read_a_foreign_label_as_unknown_not_as_none(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    foreign = await record(room, session_id, scene="S99")
    assert foreign.status_code == 200, foreign.text
    unmarked = await record(room, session_id, audio=recording(40, 2), scene=None)
    assert unmarked.status_code == 200, unmarked.text

    on_the_tablet = await read_by_b(room, session_id)
    on_the_desk = await read_by_the_reader(room, session_id)

    for read in (on_the_tablet, on_the_desk):
        assert [(each["scene"], each["scene_said"]) for each in read] == [
            (None, "recording"),
            (None, None),
        ], "quem retomava lia o rótulo que a passagem não tem como se ninguém tivesse marcado"
    assert "S99" not in str(on_the_tablet) + str(on_the_desk)


async def test_the_reader_reads_a_frase_that_arrived_after_its_restart_under_that_restart(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    room.answers.extend(["antes do recomeço", "chegou depois do recomeço"])
    await translated(room, session_id, rehearsal_id, [(0, 5000)])
    attempt = await restarted(room, session_id, rehearsal_id)
    late = await translate(room, session_id, rehearsal_id, (5000, 11000), recording(1, 600))
    assert late.status_code == 200, late.text

    (read,) = await read_by_the_reader(room, session_id)

    (restart_read,) = read["restarts"]
    assert restart_read["restart_id"] == attempt
    assert [(f["starts_ms"], f["transcript"]) for f in restart_read["frases"]] == [
        (0, "antes do recomeço"),
        (5000, "chegou depois do recomeço"),
    ]
    assert read["frases"] == []


async def test_the_reader_reads_a_held_frase_whose_restart_never_landed(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    attempt = str(uuid.uuid4())
    room.answers.append("esperando o recomeço")
    held = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=attempt
    )
    assert held.status_code == 200, held.text
    await sent(db_session, rehearsal_id)
    refused = await restart(room, session_id, rehearsal_id, attempt)
    assert refused.status_code == 409, refused.text

    (read,) = await read_by_the_reader(room, session_id)

    assert (read["frases"], read["restarts"]) == ([], [])
    (waiting,) = read["held"]
    assert waiting["attempt"] == attempt
    assert [(f["starts_ms"], f["transcript"]) for f in waiting["frases"]] == [
        (0, "esperando o recomeço")
    ]


async def test_the_readers_held_frases_leave_the_list_as_their_restarts_land(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    x, y = str(uuid.uuid4()), str(uuid.uuid4())
    assert (await restart(room, session_id, rehearsal_id, y, closes=x)).status_code == 409
    fy = await translate(
        room, session_id, rehearsal_id, (0, 6000), recording(1, 601), after_restart=y
    )
    assert (await restart(room, session_id, rehearsal_id, x)).status_code == 200
    fx = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=x
    )
    assert (fy.status_code, fx.status_code) == (200, 200)

    (read,) = await read_by_the_reader(room, session_id)
    assert [(h["attempt"], [f["ends_ms"] for f in h["frases"]]) for h in read["held"]] == [
        (y, [6000])
    ]

    assert (await restart(room, session_id, rehearsal_id, y, closes=x)).status_code == 200

    (read,) = await read_by_the_reader(room, session_id)
    assert read["held"] == []
    assert [f["ends_ms"] for f in read["frases"]] == [6000]


async def test_a_held_frase_stays_held_when_a_sibling_rehearsals_restart_of_that_attempt_lands(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    sibling_id = await recorded(room, session_id, recording(10, 2))
    z = str(uuid.uuid4())
    held = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=z
    )
    assert held.status_code == 200, held.text

    assert (await restart(room, session_id, sibling_id, z)).status_code == 200

    mine = next(
        r for r in await read_by_the_reader(room, session_id) if r["rehearsal_id"] == rehearsal_id
    )
    assert [(h["attempt"], [f["ends_ms"] for f in h["frases"]]) for h in mine["held"]] == [
        (z, [4000])
    ]


async def test_two_scenes_kept_at_once_in_one_session_take_the_next_two_numbers(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    first, second = await asyncio.gather(
        record(room, session_id, recording(5, 3)), record(room, session_id, recording(5, 4))
    )

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert sorted([first.json()["n"], second.json()["n"]]) == [1, 2]


async def test_a_scene_with_no_audio_is_refused_as_no_recording(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)

    refused = await record(room, session_id, b"")

    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"] == "A recording with no audio is not a recording"


async def test_a_frase_resent_while_it_is_still_heard_is_one_frase(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    frase = recording(1, 100)
    resent: list[httpx.Response] = []

    async def resend() -> None:
        resent.append(await translate(room, session_id, rehearsal_id, (0, 5000), frase))

    room.while_hearing.append(resend)
    first = await translate(room, session_id, rehearsal_id, (0, 5000), frase)

    assert (first.status_code, resent[0].status_code) == (200, 200), first.text
    assert await count(db_session, "ir_scene_frases", "rehearsal_id", rehearsal_id) == 1


async def test_one_read_of_a_rehearsal_reads_its_restarts_once(
    room: Room, db_session: AsyncSession, test_engine
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    attempt = await restarted(room, session_id, rehearsal_id)
    await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=attempt
    )
    said: list[str] = []

    def _heard(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        said.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", _heard)
    try:
        await read_by_b(room, session_id)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _heard)

    assert len([s for s in said if "FROM ir_scene_restarts" in s]) == 1


async def test_one_read_at_the_desk_reads_the_restarts_once(
    room: Room, db_session: AsyncSession, test_engine
) -> None:
    session_id = await a_session(db_session)
    rehearsal_id = await recorded(room, session_id)
    attempt = await restarted(room, session_id, rehearsal_id)
    await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 600), after_restart=attempt
    )
    said: list[str] = []

    def _heard(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        said.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", _heard)
    try:
        await read_by_the_reader(room, session_id)
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _heard)

    assert len([s for s in said if "FROM ir_scene_restarts" in s]) == 1
