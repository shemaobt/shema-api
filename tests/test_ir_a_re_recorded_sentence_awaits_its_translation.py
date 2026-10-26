"""A frase whose sentence was recorded again awaits its translation, and keeps its number.

Her `awaitingSplice` (src/backtranslation/store.ts at 18fa7c4): the frase stays in the telling
under the same number, the check waits for its new translation, and the re-telling at the very
span the new sentence took is what ends the wait. Her N-6 is the line for it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.services.internalization_room.sentences import AwaitingSentence, the_sentence_awaiting
from app.services.internalization_room.sessions import get_session
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX
from tests.room_harness import (
    REHEARSED_AT,
    press_terminei,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_upload_landed_at,
    upload_a_part,
)
from tests.sentence_harness import WAV, re_record, rehearsed_in_wav, seconds, spoken, wav


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture(autouse=True)
def transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    async def said(*_: Any, **__: Any) -> str:
        return "a frase nova traduzida"

    monkeypatch.setattr(segments_api, "heard", said)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _read(client: httpx.AsyncClient, session_id: str) -> dict[str, Any]:
    return (await client.get(f"{PREFIX}/sessions/{session_id}")).json()["back_translation"]


async def test_the_frase_awaits_its_translation_under_its_own_number_with_her_line(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((_, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )

    await re_record(client, session.id, middle.id, spoken(1.0))

    assert (await _read(client, session.id)).get("awaiting_segment_id") == middle.id, (
        "a sessão não dizia qual frase espera a tradução"
    )
    assert await the_sentence_awaiting(
        db_session, await get_session(db_session, session.id)
    ) == AwaitingSentence(
        segment_id=middle.id,
        frase=2,
        line="N5",
    ), "a frase regravada perdia o número ou a fala dela"


async def test_telling_the_new_sentence_at_its_own_span_ends_the_wait(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((_, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
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
    assert (await _read(client, session.id)).get("awaiting_segment_id", "") is None
    assert (
        await the_sentence_awaiting(db_session, await get_session(db_session, session.id)) is None
    ), "a frase traduzida de novo continuava esperando"


async def test_while_a_frase_awaits_no_other_frase_is_re_recorded_but_it_may_be_again(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((first, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )
    await re_record(client, session.id, middle.id, spoken(1.0), sentence_id="sentence-0005")

    other = await re_record(client, session.id, first.id, spoken(1.0), sentence_id="sentence-0006")
    again = await re_record(client, session.id, middle.id, spoken(0.5), sentence_id="sentence-0007")

    assert other.status_code == 409, other.text
    assert {key: other.json().get(key) for key in ("code", "frases")} == {
        "code": "ANOTHER_SENTENCE_AWAITS",
        "frases": [2],
    }, "uma segunda frase era regravada com a primeira ainda sem tradução"
    assert again.status_code == 200, again.text
    assert [(one["starts_ms"], one["ends_ms"]) for one in again.json()["segments"]] == [
        (0, 1000),
        (1000, 1900),
        (1900, 2900),
    ], "a frase que espera não podia ser regravada de novo"


async def test_the_awaiting_frase_is_told_only_at_the_span_the_new_sentence_took(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((_, last),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    laid = (await re_record(client, session.id, last.id, spoken(1.0))).json()["segments"][1]

    moved = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{last.id}/replace",
        data={"take_id": laid["take_id"], "starts_ms": "1000", "ends_ms": "2200"},
        files={"file": ("trecho.m4a", b"a equipe traduziu outro pedaco", "audio/mp4")},
    )
    divided = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{last.id}/divide", json={"at_ms": 1700}
    )

    assert [(one.status_code, one.json().get("code")) for one in (moved, divided)] == [
        (400, "FRASE_AWAITS_ITS_TRANSLATION"),
        (400, "FRASE_AWAITS_ITS_TRANSLATION"),
    ], "a frase que espera era traduzida noutro trecho que não o da frase nova"
    assert (await _read(client, session.id)).get("awaiting_segment_id") == last.id


async def test_the_whole_part_recorded_again_leaves_no_frase_awaiting(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((_, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )
    laid = (await re_record(client, session.id, middle.id, spoken(1.0))).json()["segments"][1]
    await the_upload_landed_at(db_session, laid["take_id"], REHEARSED_AT + timedelta(hours=1))

    uploaded = await upload_a_part(
        client, session.id, part=1, audio=wav(seconds(3.0, 1234)), content_type=WAV
    )

    assert uploaded.status_code in (200, 201), uploaded.text
    assert (await _read(client, session.id)).get("awaiting_segment_id", "") is None, (
        "a frase regravada esperava tradução numa parte que a equipe gravou inteira de novo"
    )


async def test_terminei_right_after_a_lay_in_is_refused_with_her_line_and_reads_nothing(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst = the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    session, _, ((_, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )
    new = (await re_record(client, session.id, middle.id, spoken(1.0))).json()["segments"][1]
    heard_whole = {
        "played_by_take": [
            {"take_id": new["take_id"], "played_ranges": [[0, 3400]], "clip_duration_ms": 3400}
        ]
    }

    pressed = await press_terminei(client, session.id, report=heard_whole)

    assert pressed.status_code == 200, pressed.text
    answer = pressed.json()
    assert {
        key: answer.get(key) for key in ("refusal", "untold_segment_id", "fixed_line", "checked")
    } == {
        "refusal": "FRASE_AWAITING",
        "untold_segment_id": middle.id,
        "fixed_line": "N5",
        "checked": False,
    }, "o «terminei» conferia a tradução antiga sobre a frase nova"
    named = await client.get(
        f"{PREFIX}/fixed-lines/{answer['fixed_line']}", params={"language": "pt"}
    )
    assert named.status_code == 200, (
        "a fala do «terminei» é o NOME da linha dela, lido por posição, como P2"
    )
    assert named.json()["audio_url"], "o nome N5 é servido por posição, como P2 na parte não ouvida"
    assert analyst.readings == 0, "o analista lia a passagem com a frase regravada sem tradução"
