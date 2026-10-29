"""The team repairs a frase by recording its sentence again, whole, and it is laid in its place.

Her rule of 21 September (docs/ENSAIO-FINAL-SPEC.md §6, src/draft/splice.ts at 18fa7c4): the
new sentence replaces the old one inside the part, the audio around it stays as it was, and the
frases after it move by the difference in length.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.back_translation import VoicedVerdict
from app.services.internalization_room.release import compose_internalization_release
from app.services.internalization_room.retro_export import retro_export
from app.services.internalization_room.segments import (
    current_segments,
    divide_segment,
    final_segments,
)
from app.services.internalization_room.sessions import back_translation_of, save_back_translation
from app.services.internalization_room.take_downloads import take_downloads_of
from tests.device_harness import a_linked_tablet
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX
from tests.room_harness import (
    release_blockers,
    room_client,
    stored_telling_back,
    the_bucket_is_in_memory,
    upload_a_part,
)
from tests.sentence_harness import (
    RATE,
    WAV,
    re_record,
    rehearsed_in_wav,
    samples_of,
    seconds,
    spoken,
    take_named,
    wav,
)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def test_the_new_sentence_takes_the_old_ones_place_and_the_frases_after_it_move(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, (one, two), ((first, middle, last), (other,)) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)], [(0, 2000)]]
    )

    ids = [first.id, middle.id, last.id, other.id]

    began = datetime.now(UTC)
    laid = await re_record(client, session.id, middle.id, spoken(1.0))
    ended = datetime.now(UTC)

    assert laid.status_code == 200, laid.text
    read = (await client.get(f"{PREFIX}/sessions/{session.id}")).json()
    spans = [
        (one["take_id"], one["starts_ms"], one["ends_ms"])
        for one in read["back_translation"]["segments"]
    ]
    new = spans[0][0]
    assert new not in (one.id, two.id), "a frase continuava sobre a gravação de antes"
    assert spans == [
        (new, 0, 1000),
        (new, 1000, 2400),
        (new, 2400, 3400),
        (two.id, 0, 2000),
    ], "as frases depois da nova não andavam a diferença, ou a outra parte mexia"
    assert [one["segment_id"] for one in read["back_translation"]["segments"]] == ids, (
        "as frases da parte ganhavam outro id e perdiam os achados e a história"
    )
    before = samples_of(store.objects[one.storage_key])
    after = samples_of(store.objects[(await take_named(db_session, new)).storage_key])
    assert after[:RATE] == before[:RATE], "o áudio antes da frase mudava"
    assert after[-RATE:] == before[-RATE:], "o áudio depois da frase mudava"
    await db_session.refresh(one)
    assert one.superseded_at is not None, "a parte trocada não leva a marca de quando saiu"
    assert began <= one.superseded_at <= ended
    assert (await take_named(db_session, new)).superseded_at is None
    assert (await take_named(db_session, two.id)).superseded_at is None


async def test_a_tablet_of_another_team_lays_nothing_into_this_teams_part(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, (one,), ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    stranger = await a_linked_tablet(db_session, team_id="outra-equipe")

    refused = await re_record(client, session.id, frase.id, spoken(1.0), headers=stranger.headers)

    assert refused.status_code == 404, refused.text
    assert [stretch.take_id for stretch in await final_segments(db_session, session.id)] == [
        one.id
    ], "um tablet de outra equipe regravava uma frase desta"


async def test_a_sentence_over_four_megabytes_is_refused_before_anything_is_read(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, _ = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    kept = dict(store.objects)

    refused = await re_record(
        client, session.id, "frase-que-nao-existe", b"R" * (4 * 1024 * 1024 + 1)
    )

    assert (refused.status_code, refused.json().get("code")) == (413, "SENTENCE_TOO_LONG"), (
        "uma frase de mais de 4 MB passava da porta, ou só depois de procurar a frase"
    )
    assert refused.json()["detail"] == "frase longa demais — regravem a cena", (
        "a tela não recebia as palavras dela para a frase longa"
    )
    assert store.objects == kept, "a frase longa demais deixava algo guardado"


@pytest.fixture()
def links_are_signed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _signed(bucket: str, key: str, *, expiry_minutes: int, **asked: str) -> str:
        return (
            f"https://storage.test/{bucket}/{key}?X-Goog-Expires={expiry_minutes * 60}"
            f"&disposition={asked['response_disposition']}"
        )

    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde", raising=False)
    monkeypatch.setattr(takes_service, "generate_signed_download_url", _signed)


async def test_the_raw_sentence_downloads_under_her_insert_name_for_an_hour(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    links_are_signed: None,
) -> None:
    session, _, ((frase,), _) = await rehearsed_in_wav(
        db_session, store, [[(0, 2000)], [(0, 2000)]]
    )
    laid = await re_record(client, session.id, frase.id, spoken(1.0), sentence_id="sentence-0003")
    assert laid.status_code == 200, laid.text

    (insert,) = (await take_downloads_of(db_session, session)).inserts

    assert insert.filename == "insert-S1-sentence-0003.wav"
    assert (insert.sentence_id, insert.key) == ("sentence-0003", "S1")
    link = urlsplit(insert.url)
    assert parse_qs(link.query)["X-Goog-Expires"] == ["3600"], "o link da frase não durava uma hora"
    assert parse_qs(link.query)["disposition"] == [
        'attachment; filename="insert-S1-sentence-0003.wav"'
    ]
    assert store.objects[link.path.removeprefix("/balde/")] == spoken(1.0), (
        "o link não apontava para a gravação crua da frase"
    )


async def test_the_retroverification_file_lists_each_raw_sentence_under_inserts(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
) -> None:
    session, _, ((frase,), _) = await rehearsed_in_wav(
        db_session, store, [[(0, 2000)], [(0, 2000)]]
    )
    before = (await retro_export(db_session, session, None, "internalize-x-v1")).model_dump()
    laid = await re_record(client, session.id, frase.id, spoken(1.0), sentence_id="sentence-0003")
    assert laid.status_code == 200, laid.text

    after = (await retro_export(db_session, session, None, "internalize-x-v1")).model_dump()

    assert "splices" not in before | after, "a chave splices não é servida: não guardamos carimbos"
    assert "inserts" not in before, "uma passagem sem frase regravada trazia a chave inserts"
    assert after["inserts"] == [
        {
            "spliceId": "sentence-0003",
            "clipKey": "S1",
            "filename": "insert-S1-sentence-0003.wav",
            "url": (
                f"/api/internalization-room/facilitator/sessions/{session.id}"
                "/re-recorded-sentences/sentence-0003/audio"
            ),
        }
    ]


@pytest.mark.parametrize(
    "recorded",
    [
        wav(seconds(0.3, 9000)),
        wav(seconds(0.98, 0) + seconds(0.04, 9000) + seconds(0.98, 0)),
        wav(seconds(2.0, 0)),
    ],
    ids=["a third of a second", "a blip in two seconds of silence", "two seconds of silence"],
)
async def test_a_sentence_shorter_than_half_a_second_once_trimmed_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, recorded: bytes
) -> None:
    session, (one,), ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    kept = dict(store.objects)

    refused = await re_record(client, session.id, frase.id, recorded)

    assert (refused.status_code, refused.json().get("code")) == (400, "SENTENCE_TOO_SHORT"), (
        "um toque sem frase era emendado na parte"
    )
    assert store.objects == kept
    assert [stretch.take_id for stretch in await final_segments(db_session, session.id)] == [one.id]


async def test_a_part_not_recorded_in_wav_takes_no_sentence(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    compressed, _, ((on_m4a,),) = await rehearsed_in_wav(
        db_session, store, [[(0, 2000)]], content_type="audio/mp4"
    )
    floating, (float_wav,), ((on_float,),) = await rehearsed_in_wav(
        db_session, store, [[(0, 2000)]]
    )
    store.objects[float_wav.storage_key] = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + (
        b"\x03\x00\x01\x00\x80\x3e\x00\x00\x00\xfa\x00\x00\x04\x00\x20\x00data\x00\x00\x00\x00"
    )
    kept = dict(store.objects)

    refused = [
        await re_record(client, compressed.id, on_m4a.id, spoken(1.0)),
        await re_record(client, floating.id, on_float.id, spoken(1.0)),
    ]

    assert [(one.status_code, one.json().get("code")) for one in refused] == [
        (409, "PART_NOT_WAV"),
        (409, "PART_NOT_WAV"),
    ], "uma parte que não é WAV de 16 bits recebia uma frase emendada"
    assert store.objects == kept


@pytest.mark.parametrize(
    "recorded",
    [
        b"isto nao e um wav",
        wav(seconds(1.0, 9000) * 3, rate=48000),
        wav(seconds(1.0, 9000) * 2, channels=2),
    ],
    ids=["not a wav", "another rate", "two channels"],
)
async def test_a_sentence_not_at_the_parts_own_format_is_refused_never_resampled(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, recorded: bytes
) -> None:
    session, _, ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    kept = dict(store.objects)

    refused = await re_record(client, session.id, frase.id, recorded)

    assert (refused.status_code, refused.json().get("code")) == (400, "SENTENCE_FORMAT_DIFFERS"), (
        "uma frase noutro formato era emendada como se fosse do mesmo"
    )
    assert store.objects == kept


async def test_the_take_before_and_the_raw_sentence_are_kept_and_named_on_the_session_read(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, (one,), ((_, second),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    before = store.objects[one.storage_key]
    recorded = spoken(1.0)

    await re_record(client, session.id, second.id, recorded, sentence_id="sentence-0002")

    read = (await client.get(f"{PREFIX}/sessions/{session.id}")).json()["back_translation"]
    new = read["segments"][0]["take_id"]
    assert read.get("rerecorded_sentences") == [
        {
            "sentence_id": "sentence-0002",
            "segment_id": second.id,
            "previous_take_id": one.id,
            "take_id": new,
            "starts_ms": 1000,
            "ends_ms": 2400,
        }
    ], "a sessão não dizia onde ficaram a tomada de antes e a frase gravada"
    assert (await take_named(db_session, one.id)).storage_key == one.storage_key
    assert store.objects[one.storage_key] == before, "a tomada de antes foi reescrita"
    assert recorded in store.objects.values(), "a frase como a equipe gravou não foi guardada"


async def test_a_sentence_sent_again_after_a_failure_is_laid_in_once(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((_, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )
    recorded = spoken(1.0)

    first = await re_record(client, session.id, middle.id, recorded, sentence_id="sentence-0003")
    again = await re_record(client, session.id, middle.id, recorded, sentence_id="sentence-0003")

    assert (first.status_code, again.status_code) == (200, 200), again.text
    assert again.json() == first.json(), "o reenvio respondia outra coisa"
    read = (await client.get(f"{PREFIX}/sessions/{session.id}")).json()["back_translation"]
    assert [(one["starts_ms"], one["ends_ms"]) for one in read["segments"]] == [
        (0, 1000),
        (1000, 2400),
        (2400, 3400),
    ], "o reenvio emendava a frase uma segunda vez"
    assert len(read["rerecorded_sentences"]) == 1


async def test_a_sentence_id_already_laid_in_does_not_carry_another_recording(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((_, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )
    await re_record(client, session.id, middle.id, spoken(1.0), sentence_id="sentence-0004")
    kept = dict(store.objects)

    refused = await re_record(
        client, session.id, middle.id, spoken(1.5), sentence_id="sentence-0004"
    )

    assert (refused.status_code, refused.json().get("code")) == (409, "SENTENCE_ID_REUSED"), (
        "outra gravação sob o mesmo id passava como reenvio da primeira"
    )
    assert store.objects == kept


async def test_a_sentence_laid_in_after_a_clean_check_leaves_the_passage_unchecked(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((frase, other),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    checked_at = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    state = back_translation_of(session)
    state.checked, state.checked_at = True, checked_at
    state.analysed_segment_ids = [frase.id, other.id]
    state.verdict = VoicedVerdict(clip_key="verdict.mp3")
    await save_back_translation(db_session, session, state)

    await re_record(client, session.id, frase.id, spoken(1.0))

    after = await stored_telling_back(db_session, session)
    assert (after.checked, after.verdict, after.checked_at) == (False, None, checked_at), (
        "a passagem continuava conferida sobre uma frase que ninguém traduziu"
    )
    assert "telling_back_not_checked" in await release_blockers(db_session, session)


async def test_refine_is_handed_the_part_with_the_sentence_laid_in(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, (one, two), ((_, middle), _) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)], [(0, 2000)]]
    )

    new = (await re_record(client, session.id, middle.id, spoken(1.0))).json()["segments"][1]

    packet, _ = await compose_internalization_release(db_session, session)
    assert [take["take_id"] for take in packet["audio"]["rehearsal_takes"]] == [
        new["take_id"],
        two.id,
    ], "o Refine recebia a parte de antes, sem a frase nova"
    assert one.id not in [take["take_id"] for take in packet["audio"]["rehearsal_takes"]]


async def test_a_divided_stretch_holding_the_frase_still_tiles_its_pieces(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((_, whole),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 3000)]]
    )
    first, _ = await divide_segment(db_session, session, whole, at_ms=2000)

    await re_record(client, session.id, first.id, spoken(1.0))

    spans = {
        one.id: (one.starts_ms, one.ends_ms)
        for one in await current_segments(db_session, session.id)
    }
    assert spans[whole.id] == (1000, 3400), (
        "o trecho dividido não cobria mais as suas partes depois da frase nova"
    )
    assert sorted(spans.values())[1:] == [(1000, 2400), (1000, 3400), (2400, 3400)]


async def test_a_frase_of_a_part_recorded_again_whole_takes_no_sentence(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    await upload_a_part(client, session.id, part=1, audio=wav(seconds(2.0, 77)), content_type=WAV)
    standing = [one.take_id for one in await final_segments(db_session, session.id)]
    kept = dict(store.objects)

    refused = await re_record(client, session.id, frase.id, spoken(1.0))

    assert (refused.status_code, refused.json().get("code")) == (
        400,
        "STRETCH_NO_LONGER_COUNTS",
    ), "uma frase de uma parte já regravada inteira recebia uma frase nova"
    assert store.objects == kept
    assert [one.take_id for one in await final_segments(db_session, session.id)] == standing


async def test_a_sentence_id_already_laid_in_is_not_sent_again_for_another_frase(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, _, ((first, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )
    recorded = spoken(1.0)
    await re_record(client, session.id, middle.id, recorded, sentence_id="sentence-0008")

    refused = await re_record(client, session.id, first.id, recorded, sentence_id="sentence-0008")

    assert (refused.status_code, refused.json().get("code")) == (409, "SENTENCE_ID_REUSED"), (
        "o mesmo id numa outra frase respondia como se ela tivesse recebido a frase nova"
    )
