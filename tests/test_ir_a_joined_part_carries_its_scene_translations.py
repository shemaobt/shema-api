"""ENG-1405 — a joined part carries its scene rehearsal's frases, and the bring-back lays them
again.

A part that lands with `origin` from a scene rehearsal of its own session, with that
rehearsal's own bytes, comes with the rehearsal's current frases as its told stretches: one per
frase, at its place, with its words, telling the frase's own audio. A resend lays nothing over
what the team did since, so a restart is only undone by «trazer de volta as traduções do ensaio
desta cena», which keeps the stretches told here as history.
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.hard_stretch_harness import a_session
from tests.release_harness import a_claimed_device, team_headers
from tests.room_harness import (
    played_every_part,
    the_analyst_is_scripted,
    the_analyst_reads,
    the_room_speaks,
)
from tests.scene_rehearsal_harness import (
    IR,
    Room,
    a_room,
    key_of,
    recorded,
    recording,
    sent,
    translate,
    translated,
)
from tests.sentence_harness import re_record, spoken

SCENE_MS = 10_000
FOUR_FRASES = [(0, 2000), (2000, 4500), (4500, 7000), (7000, SCENE_MS)]
FOUR_WORDS = [
    "no começo havia fome na terra",
    "a família saiu de Belém",
    "o marido morreu em Moabe",
    "os filhos casaram com moabitas",
]
TOLD_HERE = "a equipe contou esta cena de novo aqui"


@pytest.fixture()
async def room(db_session: AsyncSession, rival_factory, monkeypatch: pytest.MonkeyPatch):
    from app.services.internalization_room import takes as takes_service

    async with a_room(db_session, rival_factory, monkeypatch) as built:
        monkeypatch.setattr(takes_service, "_store", lambda *_, **__: built.bucket)
        yield built


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)


def sha(audio: bytes) -> str:
    return hashlib.sha256(audio).hexdigest()


def frase_audio(offset: int) -> bytes:
    """The bytes `translated` sends for its `offset`-th frase, at its default tone."""
    return recording(1, 100 + offset)


async def a_translated_rehearsal(
    room: Room,
    session_id: str,
    places: list[tuple[int, int]] = FOUR_FRASES,
    words: list[str] = FOUR_WORDS,
    *,
    tone: int = 3,
) -> tuple[str, bytes]:
    """A scene rehearsal of `session_id`, translated over `places` with `words`, and sent."""
    scene = recording(SCENE_MS / 1000, tone)
    rehearsal_id = await recorded(room, session_id, scene)
    room.answers.extend(words)
    await translated(room, session_id, rehearsal_id, places)
    return rehearsal_id, scene


async def join(
    room: Room,
    session_id: str,
    rehearsal_id: str,
    audio: bytes,
    *,
    part: int = 2,
    headers: dict[str, str] | None = None,
    **fields: str,
) -> httpx.Response:
    """The tablet laying the rehearsal in as part `part`, its bytes byte for byte."""
    return await room.client.post(
        f"{IR}/sessions/{session_id}/takes",
        data={
            "kind": "ensaio",
            "scope": f"parte-{part}",
            "chunk_index": str(part),
            "origin": rehearsal_id,
            "sha256": sha(audio),
            **fields,
        },
        files={"file": ("cena.wav", audio, "audio/wav")},
        headers=headers,
    )


async def joined(room: Room, session_id: str, rehearsal_id: str, audio: bytes, **kw: Any) -> str:
    answer = await join(room, session_id, rehearsal_id, audio, **kw)
    assert answer.status_code == 200, answer.text
    return str(answer.json()["take_id"])


async def recorded_as_itself(
    room: Room, session_id: str, audio: bytes, *, part: int = 2, **fields: str
) -> str:
    answer = await room.client.post(
        f"{IR}/sessions/{session_id}/takes",
        data={"kind": "ensaio", "scope": f"parte-{part}", "chunk_index": str(part), **fields},
        files={"file": ("parte.wav", audio, "audio/wav")},
    )
    assert answer.status_code == 200, answer.text
    return str(answer.json()["take_id"])


async def told_by_hand(
    room: Room, session_id: str, take_id: str, place: tuple[int, int] = (0, 2000)
) -> None:
    room.answers.append(TOLD_HERE)
    starts, ends = place
    answer = await room.client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        data={"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)},
        files={"file": ("trecho.wav", recording(1, 900), "audio/wav")},
    )
    assert answer.status_code == 200, answer.text


async def the_session(room: Room, session_id: str, **params: str) -> dict[str, Any]:
    answer = await room.client.get(f"{IR}/sessions/{session_id}", params=params)
    assert answer.status_code == 200, answer.text
    return dict(answer.json()["back_translation"])


async def stretches_on(room: Room, session_id: str, take_id: str) -> list[dict[str, Any]]:
    segments = (await the_session(room, session_id))["segments"]
    return [segment for segment in segments if segment["take_id"] == take_id]


async def places_on(room: Room, session_id: str, take_id: str) -> list[tuple[int, int]]:
    return [(s["starts_ms"], s["ends_ms"]) for s in await stretches_on(room, session_id, take_id)]


async def offered(room: Room, session_id: str) -> list[int]:
    return list((await the_session(room, session_id))["bring_back"])


async def the_file(room: Room, session_id: str) -> dict[str, Any]:
    answer = await room.client.get(
        f"{IR}/facilitator/sessions/{session_id}/retroverificacao", headers=room.desk
    )
    assert answer.status_code == 200, answer.text
    return dict(answer.json())


async def words_on(room: Room, session_id: str, take_id: str) -> list[tuple[int, int, str]]:
    return [
        (one["starts_ms"], one["ends_ms"], one["transcript"])
        for one in (await the_file(room, session_id))["stretches"]
        if one["take_id"] == take_id
    ]


async def restart_the_translation(room: Room, session_id: str) -> None:
    answer = await room.client.post(f"{IR}/sessions/{session_id}/back-translation/restart")
    assert answer.status_code == 200, answer.text


async def bring_back(room: Room, session_id: str, part: int = 2) -> httpx.Response:
    return await room.client.post(f"{IR}/sessions/{session_id}/parts/{part}/bring-back")


def the_lay_fails_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.internalization_room import joined_parts

    real = joined_parts.capture_segment
    failed: list[bool] = []

    async def capture_failing_once(*args: Any, **kwargs: Any) -> Any:
        if not failed:
            failed.append(True)
            raise RuntimeError("the database went away mid-lay")
        return await real(*args, **kwargs)

    monkeypatch.setattr(joined_parts, "capture_segment", capture_failing_once)


async def test_a_rehearsal_with_four_translated_frases_lands_as_a_part_with_four_told_stretches(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)

    part = await joined(room, session_id, rehearsal_id, scene)

    stretches = await stretches_on(room, session_id, part)
    assert [(s["starts_ms"], s["ends_ms"], s["told"], s["frase"]) for s in stretches] == [
        (0, 2000, True, 1),
        (2000, 4500, True, 2),
        (4500, 7000, True, 3),
        (7000, SCENE_MS, True, 4),
    ], "a cena juntada chegava sem as frases que a equipe já tinha traduzido no ensaio"
    assert await words_on(room, session_id, part) == [
        (starts, ends, words) for (starts, ends), words in zip(FOUR_FRASES, FOUR_WORDS, strict=True)
    ]
    for offset, stretch in enumerate(stretches):
        played = await room.client.get(
            f"{IR}/sessions/{session_id}/takes/{stretch['bridge_take_id']}/audio"
        )
        assert played.status_code == 307, played.text
        assert played.headers["location"].endswith(key_of(room, frase_audio(offset))), (
            "o trecho contado não tocava a própria voz da frase"
        )


async def test_a_replaced_frase_is_not_laid_only_the_frase_that_replaced_it(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(
        room, session_id, [(0, 4000), (4000, SCENE_MS)], ["a primeira", "a segunda"]
    )
    (first, _second) = [
        frase["frase_id"]
        for frase in (await room.client.get(f"{IR}/sessions/{session_id}/scene-rehearsals")).json()[
            "scene_rehearsals"
        ][0]["frases"]
    ]
    room.answers.append("a primeira traduzida de novo")
    again = await translate(
        room, session_id, rehearsal_id, (0, 4000), recording(1, 700), replaces=first
    )
    assert again.status_code == 200, again.text
    await sent(db_session, rehearsal_id)

    part = await joined(room, session_id, rehearsal_id, scene)

    assert await words_on(room, session_id, part) == [
        (0, 4000, "a primeira traduzida de novo"),
        (4000, SCENE_MS, "a segunda"),
    ], "a frase substituída voltava junto com a que a substituiu"


async def test_a_rehearsal_with_untranslated_ground_lands_with_that_stretch_untold_and_the_listen_names_it_n3(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(
        room, session_id, [(0, 4000), (5500, SCENE_MS)], ["antes do buraco", "depois do buraco"]
    )
    await sent(db_session, rehearsal_id)
    part = await joined(room, session_id, rehearsal_id, scene)

    listened = await room.client.post(
        f"{IR}/sessions/{session_id}/back-translation/listened-whole",
        json=played_every_part([part], duration_ms=SCENE_MS),
    )

    assert listened.status_code == 200, listened.text
    body = listened.json()
    assert body["refusal"] == "STRETCH_UNTRANSLATED"
    assert [(one["take_id"], one["from_ms"]) for one in body["untranslated"]] == [(part, 4000)]
    assert await places_on(room, session_id, part) == [(0, 4000), (5500, SCENE_MS)], (
        "o chão que ninguém traduziu ganhava um trecho que ninguém contou"
    )


async def test_the_same_rehearsal_joined_again_leaves_the_stretches_unchanged(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    part = await joined(room, session_id, rehearsal_id, scene)
    before = await stretches_on(room, session_id, part)
    words = await words_on(room, session_id, part)
    assert len(before) == len(FOUR_FRASES)

    again = await joined(room, session_id, rehearsal_id, scene)
    from_b = await joined(room, session_id, rehearsal_id, scene, headers=room.tablet_b)

    assert again == from_b == part
    assert await stretches_on(room, session_id, part) == before, (
        "juntar de novo a mesma cena escrevia os trechos outra vez"
    )
    assert await words_on(room, session_id, part) == words


async def test_after_a_restart_a_resend_of_the_join_lays_nothing_and_the_part_is_offered_its_bring_back(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    part = await joined(room, session_id, rehearsal_id, scene)
    await restart_the_translation(room, session_id)
    assert await places_on(room, session_id, part) == []

    await joined(room, session_id, rehearsal_id, scene)

    assert await places_on(room, session_id, part) == [], (
        "o reenvio da junção desfazia calado o recomeço da tradução"
    )
    assert await offered(room, session_id) == [2]


async def test_the_bring_back_lays_the_rehearsals_frases_again_and_keeps_the_ones_told_here_as_history(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    part = await joined(room, session_id, rehearsal_id, scene)
    await restart_the_translation(room, session_id)
    await told_by_hand(room, session_id, part)

    answered = await bring_back(room, session_id)

    assert answered.status_code == 200, answered.text
    assert await words_on(room, session_id, part) == [
        (starts, ends, words) for (starts, ends), words in zip(FOUR_FRASES, FOUR_WORDS, strict=True)
    ]
    assert TOLD_HERE in [
        one["transcript"] for one in (await the_file(room, session_id))["abandoned"]
    ], "o que a equipe contou aqui sumia em vez de ficar guardado"
    assert await offered(room, session_id) == []


async def test_a_bring_back_sent_twice_lays_once(room: Room, db_session: AsyncSession) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    part = await joined(room, session_id, rehearsal_id, scene)
    await restart_the_translation(room, session_id)
    first = await bring_back(room, session_id)
    assert first.status_code == 200, first.text
    laid = [s["segment_id"] for s in await stretches_on(room, session_id, part)]
    assert len(laid) == len(FOUR_FRASES)

    second = await bring_back(room, session_id)

    assert second.status_code == 200, second.text
    assert [s["segment_id"] for s in await stretches_on(room, session_id, part)] == laid, (
        "o segundo toque trazia as frases de volta outra vez"
    )


async def test_a_joined_part_whose_frases_never_landed_is_offered_its_bring_back_and_the_resend_lays_them(  # noqa: E501
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    the_lay_fails_once(monkeypatch)
    with pytest.raises(RuntimeError):
        await join(room, session_id, rehearsal_id, scene)
    taken = await room.client.get(f"{IR}/sessions/{session_id}/takes")
    (part,) = [one["take_id"] for one in taken.json()["takes"] if one["origin"] == rehearsal_id]
    assert await offered(room, session_id) == [2]
    assert await places_on(room, session_id, part) == []

    await joined(room, session_id, rehearsal_id, scene)

    assert await places_on(room, session_id, part) == FOUR_FRASES, (
        "o reenvio da caixa de saída não curava uma junção cujas frases nunca chegaram"
    )
    assert await offered(room, session_id) == []


async def test_a_joined_part_the_team_told_by_hand_before_its_frases_landed_is_offered_its_bring_back(  # noqa: E501
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    the_lay_fails_once(monkeypatch)
    with pytest.raises(RuntimeError):
        await join(room, session_id, rehearsal_id, scene)
    taken = await room.client.get(f"{IR}/sessions/{session_id}/takes")
    (part,) = [one["take_id"] for one in taken.json()["takes"] if one["origin"] == rehearsal_id]
    await told_by_hand(room, session_id, part)

    assert await offered(room, session_id) == [2]
    await joined(room, session_id, rehearsal_id, scene)

    assert await words_on(room, session_id, part) == [(0, 2000, TOLD_HERE)], (
        "o reenvio da junção passava por cima do que a equipe contou à mão"
    )


async def test_a_part_a_sentence_was_re_recorded_in_is_never_offered_and_the_door_refuses(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    part = await joined(room, session_id, rehearsal_id, scene)
    first = (await stretches_on(room, session_id, part))[0]
    laid_in = await re_record(room.client, session_id, first["segment_id"], spoken(1.0))
    assert laid_in.status_code == 200, laid_in.text
    await restart_the_translation(room, session_id)
    before = (await the_session(room, session_id))["segments"]

    refused = await bring_back(room, session_id)

    assert await offered(room, session_id) == []
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "NOTHING_TO_BRING_BACK"
    assert (await the_session(room, session_id))["segments"] == before


async def test_a_part_joined_from_the_other_language_sessions_rehearsal_is_not_laid_nor_offered(
    room: Room, db_session: AsyncSession
) -> None:
    portuguese = await a_session(db_session, language="pt")
    english = await a_session(db_session, language="en")
    rehearsal_id, scene = await a_translated_rehearsal(
        room, english, words=["in the beginning", "they left", "he died", "they married"]
    )
    await sent(db_session, rehearsal_id)

    part = await joined(room, portuguese, rehearsal_id, scene)

    assert await places_on(room, portuguese, part) == [], (
        "frases em inglês iam para baixo de uma conferência em português"
    )
    assert await offered(room, portuguese) == []
    refused = await bring_back(room, portuguese)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "NOTHING_TO_BRING_BACK"


async def test_a_joined_part_laid_over_a_part_recorded_again_leaves_nothing_waiting_to_be_told_again(  # noqa: E501
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    by_hand = await recorded_as_itself(room, session_id, recording(SCENE_MS / 1000, 50))
    await told_by_hand(room, session_id, by_hand)

    await joined(room, session_id, rehearsal_id, scene, over_take=by_hand)

    read = await the_session(room, session_id, include_stale="true")
    assert [s for s in read["segments"] if s["stale"]] == [], (
        "a junção deixava a equipe convidada a contar de novo o que as frases já cobrem"
    )
    assert TOLD_HERE in [
        one["transcript"] for one in (await the_file(room, session_id))["abandoned"]
    ]


async def test_a_bring_back_under_a_number_with_no_part_is_not_found(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    await joined(room, session_id, rehearsal_id, scene)
    await restart_the_translation(room, session_id)

    missing = await bring_back(room, session_id, part=7)

    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "NOT_FOUND"
    assert (await the_session(room, session_id))["segments"] == []
    assert (await bring_back(room, session_id, part=2)).status_code == 200, (
        "a porta não existia: o 404 era da rota, não da parte"
    )


async def test_a_bring_back_over_a_checked_telling_undoes_the_check(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    part = await joined(room, session_id, rehearsal_id, scene)
    await restart_the_translation(room, session_id)
    await told_by_hand(room, session_id, part, (0, SCENE_MS))
    listened = await room.client.post(
        f"{IR}/sessions/{session_id}/back-translation/listened-whole",
        json=played_every_part([part], duration_ms=SCENE_MS),
    )
    assert listened.status_code == 200, listened.text
    finished = await room.client.post(f"{IR}/sessions/{session_id}/back-translation/finish")
    assert finished.status_code == 200, finished.text
    assert (await the_session(room, session_id))["checked"] is True

    answered = await bring_back(room, session_id)

    assert answered.status_code == 200, answered.text
    assert (await the_session(room, session_id))["checked"] is False, (
        "as frases trazidas de volta ficavam sob uma conferência que nunca as leu"
    )


async def test_a_scene_with_a_frase_of_150_ms_joins_and_its_other_frases_become_stretches(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(
        room, session_id, [(0, 150), (150, SCENE_MS)], ["um suspiro", "o resto da cena"]
    )
    await sent(db_session, rehearsal_id)

    first = await join(room, session_id, rehearsal_id, scene)
    again = await join(room, session_id, rehearsal_id, scene)

    assert first.status_code == again.status_code == 200, (first.text, again.text)
    assert await offered(room, session_id) == [], (
        "a frase curta sozinha oferecia trazer de volta o que nunca pode ser trecho"
    )
    assert await words_on(room, session_id, first.json()["take_id"]) == [
        (150, SCENE_MS, "o resto da cena")
    ], "uma frase curta demais para ser trecho travava a junção da cena inteira"


async def test_a_bring_back_takes_the_findings_on_the_stretches_it_abandons_with_them(
    room: Room, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    part = await joined(room, session_id, rehearsal_id, scene)
    await restart_the_translation(room, session_id)
    await told_by_hand(room, session_id, part, (0, SCENE_MS))
    listened = await room.client.post(
        f"{IR}/sessions/{session_id}/back-translation/listened-whole",
        json=played_every_part([part], duration_ms=SCENE_MS),
    )
    assert listened.status_code == 200, listened.text
    analyst.readings = [{"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 1}]}]
    finished = await room.client.post(f"{IR}/sessions/{session_id}/back-translation/finish")
    assert finished.status_code == 200, finished.text
    assert [one["note"] for one in (await the_file(room, session_id))["findings"]] == [
        "Rute foi junto"
    ]

    answered = await bring_back(room, session_id)

    assert answered.status_code == 200, answered.text
    assert (await the_file(room, session_id))["findings"] == [], (
        "o achado sobre o trecho abandonado seguia aberto sobre as frases trazidas de volta"
    )


async def test_a_tablet_of_another_team_cannot_bring_this_teams_frases_back(
    room: Room, db_session: AsyncSession
) -> None:
    session_id = await a_session(db_session, language="pt")
    rehearsal_id, scene = await a_translated_rehearsal(room, session_id)
    await sent(db_session, rehearsal_id)
    await joined(room, session_id, rehearsal_id, scene)
    await restart_the_translation(room, session_id)
    _stranger, credential = await a_claimed_device(db_session, email="estranho@example.com")

    refused = await room.client.post(
        f"{IR}/sessions/{session_id}/parts/2/bring-back", headers=team_headers(credential)
    )

    assert refused.status_code == 404, refused.text
    assert (await the_session(room, session_id))["segments"] == [], (
        "um tablet de outra equipe trazia de volta as frases desta"
    )
