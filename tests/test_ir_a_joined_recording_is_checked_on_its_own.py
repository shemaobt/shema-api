"""ENG-1207 — a joined recording is checked on its own, and an untranslated stretch gets N-3.

Her join lays each scene rehearsal into the passage recording as a clip that remembers where it
came from, and only such a recording changes what follows the listen (`ensaioFinal.ts:431-483`
at her freeze): a stretch nobody translated sends the team back to it with her N-3, and a
recording translated through is checked once with no tap, after her N-2. A recording no join
touched checks exactly as before.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSceneRehearsal, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.segments import capture_segment
from app.services.internalization_room.takes import takes_of
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import (
    REHEARSED_AT,
    TABLET,
    Analyst,
    Room,
    a_piece_still_to_be_told,
    another_rehearsal_take,
    nothing_is_read_ahead,
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    stretch_on,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken, take_named

PART_MS = 4000
CHECKING_BY_POSITION = "N1"
UNTRANSLATED_BY_POSITION = "N2"


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    return the_analyst_reads(monkeypatch)


@pytest.fixture(autouse=True)
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    nothing_is_read_ahead(monkeypatch)


@pytest.fixture(autouse=True)
def transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    async def said(*_: Any, **__: Any) -> str:
        return "a frase nova traduzida"

    monkeypatch.setattr(segments_api, "heard", said)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _a_scene_rehearsal(db: AsyncSession, session: IRSession, n: int) -> IRSceneRehearsal:
    rehearsal = IRSceneRehearsal(
        session_id=session.id,
        project_id=session.project_id,
        pericope=session.pericope,
        n=n,
        device_id=TABLET,
        storage_key=f"scene-rehearsals/{session.id}/{n}",
        size_bytes=2048,
        sha256=chr(ord("p") + n) * 64,
        crc32c="AAAAAAA=",
        content_type="audio/wav",
        duration_ms=4000,
        scene=f"S{n}",
    )
    db.add(rehearsal)
    await db.commit()
    return rehearsal


async def _recorded(
    db: AsyncSession,
    frases_by_part: list[list[tuple[int, int]]],
    *,
    joined: bool = True,
    content_type: str = "audio/wav",
) -> tuple[IRSession, list[IRTake]]:
    """A passage recorded in one part per scene, each told back over the spans it names.

    `frases_by_part[i]` are the spans, in the part's own milliseconds, of the translated frases
    on scene i+1; an empty list is a scene nobody translated anything over. `joined` lays each
    part in from that scene's rehearsal, as the join does; without it the team recorded them.
    """
    session, _ = await rehearsed_in_parts(db, 0)
    parts = []
    for index, spans in enumerate(frases_by_part):
        number = index + 1
        rehearsal = await _a_scene_rehearsal(db, session, number) if joined else None
        take = IRTake(
            session_id=session.id,
            project_id=session.project_id,
            device_id=TABLET,
            pericope=session.pericope,
            kind=IRTakeKind.ENSAIO,
            scope=f"parte-{number}",
            ordinal=number,
            storage_key=f"takes/{session.id}/ensaio/{number}",
            size_bytes=2048,
            sha256=chr(ord("a") + index) * 64,
            crc32c="AAAAAAA=",
            content_type=content_type,
            created_at=REHEARSED_AT + timedelta(minutes=index),
            origin=rehearsal.id if rehearsal else None,
        )
        db.add(take)
        await db.commit()
        for starts_ms, ends_ms in spans:
            await capture_segment(
                db,
                session,
                take_id=take.id,
                starts_ms=starts_ms,
                ends_ms=ends_ms,
                bridge_take_id=f"retro-{number}-{starts_ms}",
                transcript=f"a cena {number} contada de volta",
            )
        parts.append(take)
    return session, parts


def _heard(parts: list[IRTake]) -> dict[str, Any]:
    return played_every_part([part.id for part in parts], duration_ms=PART_MS)


async def _listened_whole(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    report: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/listened-whole",
        **({"json": report} if report is not None else {}),
        **({"headers": headers} if headers is not None else {}),
    )


async def _joined_upload(
    client: httpx.AsyncClient, session_id: str, *, part: int, origin: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Device": TABLET},
        data={
            "kind": "ensaio",
            "scope": f"parte-{part}",
            "chunk_index": str(part),
            "origin": origin,
        },
        files={"file": ("cena.wav", f"cena {part}".encode(), "audio/wav")},
    )


async def test_a_part_joined_from_a_scene_rehearsal_keeps_where_it_came_from(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    rehearsal = await _a_scene_rehearsal(db_session, session, 1)

    answered = await _joined_upload(client, session.id, part=1, origin=rehearsal.id)

    assert answered.status_code == 200, answered.text
    (take,) = await takes_of(db_session, session.id)
    assert take.origin == rehearsal.id, "a parte juntada esquecia de que ensaio veio"


async def test_the_take_listing_names_the_scene_rehearsal_a_joined_part_came_from(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    rehearsal = await _a_scene_rehearsal(db_session, session, 1)
    await _joined_upload(client, session.id, part=1, origin=rehearsal.id)

    listed = await client.get(
        f"{PREFIX}/sessions/{session.id}/takes", headers={"X-Room-Device": TABLET}
    )

    assert listed.status_code == 200, listed.text
    (part,) = listed.json()["takes"]
    assert (part["ordinal"], part["origin"]) == (1, rehearsal.id), (
        "o tablet que retoma não sabia que a parte era juntada"
    )


async def test_a_part_recorded_as_itself_names_no_origin_in_the_listing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)
    await client.post(
        f"{PREFIX}/sessions/{session.id}/takes",
        headers={"X-Room-Device": TABLET},
        data={"kind": "ensaio", "scope": "parte-1", "chunk_index": "1"},
        files={"file": ("parte.wav", b"parte 1", "audio/wav")},
    )

    listed = await client.get(
        f"{PREFIX}/sessions/{session.id}/takes", headers={"X-Room-Device": TABLET}
    )

    (part,) = listed.json()["takes"]
    assert part["origin"] is None, "uma parte gravada pela equipe aparecia como juntada"


async def test_an_origin_that_names_no_scene_rehearsal_of_the_passage_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 0)

    answered = await _joined_upload(client, session.id, part=1, origin="ensaio-que-nao-existe")

    assert answered.status_code == 422, answered.text
    assert await takes_of(db_session, session.id) == [], (
        "uma origem inventada fazia da gravação uma junção que nunca houve"
    )


async def test_terminei_over_a_joined_scene_with_no_frase_is_refused_with_n3_naming_that_scene(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, (first, second, third) = await _recorded(
        db_session, [[(0, PART_MS)], [], [(0, PART_MS)]]
    )

    answered = await press_terminei(client, session.id, report=_heard([first, second, third]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "STRETCH_UNTRANSLATED", (
        "uma cena juntada sem frase nenhuma ia para a conferência como se estivesse traduzida"
    )
    assert body["fixed_line"] == UNTRANSLATED_BY_POSITION
    assert body["untranslated"] == [{"take_id": second.id, "scene": 2, "from_ms": 0}]
    assert body["checked"] is False
    assert analyst.readings == 0
    assert (await stored_telling_back(db_session, session)).checks == []


async def test_an_unheard_joined_scene_is_refused_as_unheard_before_untranslated(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (first, second) = await _recorded(db_session, [[(0, PART_MS)], []])

    answered = await press_terminei(client, session.id, report=_heard([first]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "PART_UNHEARD", (
        "ela recusa o que não foi ouvido antes do que falta traduzir"
    )
    assert body["unheard_take_ids"] == [second.id]
    assert body["untranslated"] == []


async def test_a_joined_recording_with_nothing_translated_names_every_scene_still_to_translate(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, (first, second) = await _recorded(db_session, [[], []])

    answered = await press_terminei(client, session.id, report=_heard([first, second]))

    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refusal"] == "STRETCH_UNTRANSLATED", (
        "numa junção sem tradução nenhuma ela manda às cenas, não diz que não há frase"
    )
    assert body["untranslated"] == [
        {"take_id": first.id, "scene": 1, "from_ms": 0},
        {"take_id": second.id, "scene": 2, "from_ms": 0},
    ]
    assert analyst.readings == 0


async def test_the_first_full_listen_of_a_joined_recording_translated_through_checks_it_with_n2(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, parts = await _recorded(db_session, [[(0, PART_MS)], [(0, 1500), (1500, PART_MS)]])

    listened = await _listened_whole(client, session.id, report=_heard(parts))

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["automatic_check"] is True, "a junção traduzida inteira esperava um toque"
    assert body["fixed_line"] == CHECKING_BY_POSITION
    assert analyst.readings == 0, "a porta da escuta conferia antes de a voz dizer o N-2"

    checked = await press_terminei(client, session.id)

    assert checked.status_code == 200, checked.text
    assert checked.json()["refusal"] is None, (
        "a escuta inteira não ficou guardada para a conferência"
    )
    assert analyst.readings == 1
    assert len((await stored_telling_back(db_session, session)).checks) == 1


async def test_a_tablet_of_another_team_cannot_report_this_teams_listen(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await _recorded(db_session, [[(0, PART_MS)]])
    _stranger, credential = await a_claimed_device(db_session, email="estranho@example.com")

    refused = await _listened_whole(
        client, session.id, report=_heard(parts), headers=team_headers(credential)
    )

    assert refused.status_code == 404, refused.text
    assert (await stored_telling_back(db_session, session)).played_by_take == [], (
        "um tablet de outra equipe guardava a escuta desta"
    )


async def test_a_recording_no_join_touched_is_never_checked_by_its_listen(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await _recorded(db_session, [[(0, PART_MS)], [(0, PART_MS)]], joined=False)

    listened = await _listened_whole(client, session.id, report=_heard(parts))

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["automatic_check"] is False, (
        "uma gravação que nenhuma junção tocou era conferida sem o «terminei» da equipe"
    )
    assert body["fixed_line"] == ""


async def test_a_joined_recording_already_checked_is_not_checked_again_by_the_next_listen(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, parts = await _recorded(db_session, [[(0, PART_MS)], [(0, PART_MS)]])
    first = await _listened_whole(client, session.id, report=_heard(parts))
    assert first.json()["automatic_check"] is True
    assert (await press_terminei(client, session.id)).status_code == 200

    again = await _listened_whole(client, session.id, report=_heard(parts))

    assert again.status_code == 200, again.text
    body = again.json()
    assert body["automatic_check"] is False, (
        "a conferência automática corria de novo na segunda escuta"
    )
    assert body["fixed_line"] == ""
    assert analyst.readings == 1


async def test_after_the_translation_starts_over_the_next_listen_checks_on_its_own_again(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, parts = await _recorded(db_session, [[(0, PART_MS)], [(0, PART_MS)]])
    await _listened_whole(client, session.id, report=_heard(parts))
    assert (await press_terminei(client, session.id)).status_code == 200
    restarted = await client.post(f"{PREFIX}/sessions/{session.id}/back-translation/restart")
    assert restarted.status_code == 200, restarted.text
    for part in parts:
        await capture_segment(
            db_session,
            session,
            take_id=part.id,
            starts_ms=0,
            ends_ms=PART_MS,
            bridge_take_id=f"retro-de-novo-{part.ordinal}",
            transcript="contada de volta outra vez",
        )

    listened = await _listened_whole(client, session.id, report=_heard(parts))

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["automatic_check"] is True, (
        "depois de recomeçar a tradução a junção traduzida de novo esperava um toque"
    )
    assert body["fixed_line"] == CHECKING_BY_POSITION


async def test_a_listen_that_left_a_joined_scene_unheard_checks_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (first, _second) = await _recorded(db_session, [[(0, PART_MS)], [(0, PART_MS)]])

    listened = await _listened_whole(client, session.id, report=_heard([first]))

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["automatic_check"] is False, "uma cena que ninguém ouviu ia para a conferência"
    assert body["fixed_line"] == ""


async def test_a_listen_with_a_frase_awaiting_its_translation_checks_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await _recorded(db_session, [[(0, PART_MS)], [(0, PART_MS)]])
    await a_piece_still_to_be_told(
        db_session, session, await stretch_on(db_session, session, parts[1])
    )

    listened = await _listened_whole(client, session.id, report=_heard(parts))

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["automatic_check"] is False, (
        "a conferência corria por cima de uma frase sem tradução"
    )
    assert body["fixed_line"] == ""


async def test_a_listen_of_a_joined_recording_that_carried_no_translation_checks_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, parts = await _recorded(db_session, [[], []])

    listened = await _listened_whole(client, session.id, report=_heard(parts))

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["automatic_check"] is False, (
        "sem tradução nenhuma trazida a tradução começa como hoje, não com a conferência"
    )
    assert body["fixed_line"] == ""


@pytest.mark.parametrize(
    ("second_scene", "from_ms"),
    [([(0, 1000), (3000, PART_MS)], 1000), ([], 0)],
    ids=["two seconds nobody translated", "a scene with no frase"],
)
async def test_a_listen_over_a_joined_stretch_nobody_translated_sends_the_team_there_with_n3(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: Analyst,
    second_scene: list[tuple[int, int]],
    from_ms: int,
) -> None:
    session, parts = await _recorded(db_session, [[(0, PART_MS)], second_scene])

    listened = await _listened_whole(client, session.id, report=_heard(parts))

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["automatic_check"] is False, (
        "a conferência automática corria por cima de um trecho sem tradução"
    )
    assert body["refusal"] == "STRETCH_UNTRANSLATED"
    assert body["fixed_line"] == UNTRANSLATED_BY_POSITION
    assert body["untranslated"] == [{"take_id": parts[1].id, "scene": 2, "from_ms": from_ms}]
    assert analyst.readings == 0


@pytest.mark.parametrize(
    ("frases", "content_type", "untranslated_from"),
    [
        ([(0, 1000), (1499, PART_MS)], "audio/wav", None),
        ([(0, 1000), (1500, PART_MS)], "audio/wav", 1000),
        ([(0, 3501)], "audio/wav", None),
        ([(0, 3500)], "audio/wav", 3500),
        ([(0, 1000), (3000, PART_MS)], "audio/mp4", None),
    ],
    ids=[
        "a hole just under half a second",
        "a hole of half a second",
        "a tail just under half a second",
        "a tail of half a second",
        "two seconds on a recording that is not WAV",
    ],
)
async def test_only_half_a_second_or_more_of_a_wav_part_counts_as_a_stretch_untranslated(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    frases: list[tuple[int, int]],
    content_type: str,
    untranslated_from: int | None,
) -> None:
    session, (part,) = await _recorded(db_session, [frases], content_type=content_type)

    listened = await _listened_whole(client, session.id, report=_heard([part]))

    assert listened.status_code == 200, listened.text
    body = listened.json()
    if untranslated_from is None:
        assert body["automatic_check"] is True, "um resto sem fala nenhuma barrava a conferência"
        assert body["untranslated"] == []
    else:
        assert body["refusal"] == "STRETCH_UNTRANSLATED", "meio segundo sem tradução passava"
        assert body["untranslated"] == [
            {"take_id": part.id, "scene": 1, "from_ms": untranslated_from}
        ]


async def test_terminei_over_a_joined_stretch_that_held_only_silence_is_checked_on_their_word(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: Analyst
) -> None:
    session, parts = await _recorded(db_session, [[(0, PART_MS)], [(0, 1000), (3000, PART_MS)]])

    answered = await press_terminei(client, session.id, report=_heard(parts))

    assert answered.status_code == 200, answered.text
    assert answered.json()["refusal"] is None, (
        "o «terminei» da equipe não fechava à mão um trecho onde nada foi dito"
    )
    assert analyst.readings == 1


async def _joined_in_wav(
    db: AsyncSession, store: MemoryStore, frases: list[tuple[int, int]]
) -> tuple[IRSession, IRTake, list[Any], str]:
    session, (part,), (told,) = await rehearsed_in_wav(db, store, [frases])
    rehearsal = await _a_scene_rehearsal(db, session, 1)
    part.origin = rehearsal.id
    await db.commit()
    return session, part, told, rehearsal.id


async def test_a_sentence_laid_into_a_joined_part_leaves_the_recording_joined(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, (_, middle), origin = await _joined_in_wav(
        db_session, store, [(0, 1000), (1000, 2000)]
    )
    untold = await another_rehearsal_take(
        db_session, session, sha256="z" * 64, scope="parte-2", ordinal=2
    )
    laid = (await re_record(client, session.id, middle.id, spoken(1.0))).json()["segments"][1]
    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{middle.id}/replace",
        data={
            "take_id": laid["take_id"],
            "starts_ms": str(laid["starts_ms"]),
            "ends_ms": str(laid["ends_ms"]),
        },
        files={"file": ("trecho.m4a", b"a equipe traduziu a frase nova", "audio/mp4")},
    )
    assert told.status_code == 200, told.text

    answered = await press_terminei(
        client,
        session.id,
        report=played_every_part([laid["take_id"], untold.id], duration_ms=laid["ends_ms"]),
    )

    assert (await take_named(db_session, laid["take_id"])).origin == origin, (
        "a frase regravada desfazia a junção da parte"
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["refusal"] == "STRETCH_UNTRANSLATED"
    assert answered.json()["untranslated"] == [{"take_id": untold.id, "scene": 2, "from_ms": 0}]


async def test_a_listen_with_a_re_recorded_sentence_awaiting_its_words_checks_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, (_, middle), _ = await _joined_in_wav(db_session, store, [(0, 1000), (1000, 2000)])
    laid = (await re_record(client, session.id, middle.id, spoken(1.0))).json()["segments"][1]

    listened = await _listened_whole(
        client,
        session.id,
        report=played_every_part([laid["take_id"]], duration_ms=laid["ends_ms"]),
    )

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["automatic_check"] is False, (
        "a voz dizia o N-2 com uma frase regravada ainda sem tradução, e a conferência recusava"
    )
    assert body["fixed_line"] == ""
