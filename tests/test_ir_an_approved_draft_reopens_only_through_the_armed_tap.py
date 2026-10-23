"""ENG-1260 — an approved draft is re-opened through a door only with the team's armed tap.

Over an approved draft, a join that puts a new take in place, a swap, a whole take over a joined
recording and a re-recorded sentence are refused `DRAFT_APPROVED` (409) unless the request says
the team armed the tap (`reopens_the_approved_draft`): nothing is stored and the draft stays
approved. Her join and splice refuse a finalized draft without `reopen` (join.ts:204,
splice.ts:157 at 18fa7c4). A part recorded on the recording screen takes one tap and re-opens
the draft, and a join that finds the same take already kept brings nothing new.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSceneRehearsal, IRSession
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import capture_segment, final_segments
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, P, reported_playback, team_release
from tests.room_harness import (
    PART_MS,
    TABLET,
    nothing_is_read_ahead,
    rehearsed_in_parts,
    room_client,
    the_analyst_reads,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken

REOPENS = {"reopens_the_approved_draft": "true"}


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    the_analyst_reads(monkeypatch)
    the_room_speaks(monkeypatch)
    nothing_is_read_ahead(monkeypatch)

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


async def _kept(
    client: httpx.AsyncClient,
    session_id: str,
    *,
    audio: bytes,
    part: int | None,
    origin: str | None = None,
    reopens: bool = False,
) -> httpx.Response:
    data = {"kind": "ensaio", "scope": "passagem-inteira" if part is None else f"parte-{part}"}
    if part is not None:
        data["chunk_index"] = str(part)
    if origin is not None:
        data["origin"] = origin
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Device": TABLET},
        data=data | (REOPENS if reopens else {}),
        files={"file": ("cena.wav", audio, "audio/wav")},
    )


async def _recorded(
    client: httpx.AsyncClient, db: AsyncSession, *, joined: bool
) -> tuple[IRSession, list[str]]:
    """A passage kept in two parts through the keep door, each told back over its whole length.

    `joined` lays each part in from its scene's rehearsal, as the join does; without it the team
    recorded them on the recording screen.
    """
    session, _ = await rehearsed_in_parts(db, 0)
    origins = []
    for part in (1, 2):
        origin = (await _a_scene_rehearsal(db, session, part)).id if joined else None
        kept = await _kept(
            client, session.id, audio=f"cena {part}".encode(), part=part, origin=origin
        )
        assert kept.status_code == 200, kept.text
        await capture_segment(
            db,
            session,
            take_id=kept.json()["take_id"],
            starts_ms=0,
            ends_ms=PART_MS,
            bridge_take_id=f"retro-{part}",
            transcript=f"a cena {part} contada de volta",
        )
        origins.append(origin)
    return session, origins


async def _approved(client: httpx.AsyncClient, db: AsyncSession, session: IRSession) -> None:
    """The team checks the telling-back clean, hears every part, and approves."""
    told = await final_segments(db, session.id)
    await reported_playback(
        db,
        session,
        BackTranslationState(
            scope=session.pericope,
            findings=[],
            checked=True,
            analysed_segment_ids=[one.id for one in told],
        ),
    )
    answered = await client.post(team_release(session.id))
    assert answered.status_code == 200, answered.text
    assert answered.json()["version"] is not None, answered.text


async def _approval(client: httpx.AsyncClient, session_id: str) -> dict[str, Any] | None:
    read = await client.get(f"{PREFIX}/sessions/{session_id}")
    assert read.status_code == 200, read.text
    approval: dict[str, Any] | None = read.json()["approved"]
    return approval


async def _takes(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    listed = await client.get(f"{PREFIX}/sessions/{session_id}/takes")
    assert listed.status_code == 200, listed.text
    takes: list[dict[str, Any]] = listed.json()["takes"]
    return takes


async def _marked(client: httpx.AsyncClient) -> bool:
    answered = await client.get(f"{PREFIX}/books/Ruth/passages?language=pt")
    assert answered.status_code == 200, answered.text
    marks = {entry["pericope"]: entry["approved"] for entry in answered.json()["passages"]}
    return bool(marks[P])


async def _a_frase_of_an_approved_draft(
    client: httpx.AsyncClient, db: AsyncSession, store: MemoryStore
) -> tuple[IRSession, str]:
    session, _parts, frases = await rehearsed_in_wav(db, store, [[(0, 1000), (1000, 2000)]])
    await _approved(client, db, session)
    return session, frases[0][0].id


async def test_a_re_recorded_sentence_over_an_approved_draft_without_the_armed_tap_is_refused_and_the_draft_stays_approved(  # noqa: E501
    client, db_session, store
) -> None:
    session, frase = await _a_frase_of_an_approved_draft(client, db_session, store)
    takes_before = await _takes(client, session.id)
    told_before = await final_segments(db_session, session.id)
    stored_before = dict(store.objects)

    refused = await re_record(client, session.id, frase, spoken(1.0))

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "DRAFT_APPROVED"
    assert (await _approval(client, session.id) or {}).get("version") == 1
    assert await _takes(client, session.id) == takes_before
    assert [
        (one.id, one.take_id, one.starts_ms, one.ends_ms)
        for one in await final_segments(db_session, session.id)
    ] == [(one.id, one.take_id, one.starts_ms, one.ends_ms) for one in told_before]
    assert store.objects == stored_before
    assert await _marked(client) is True


async def test_the_same_sentence_with_the_armed_tap_is_laid_in_and_re_opens_the_draft(
    client, db_session, store
) -> None:
    session, frase = await _a_frase_of_an_approved_draft(client, db_session, store)

    laid = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{frase}/sentence",
        data={"sentence_id": "sentence-0001"} | REOPENS,
        files={"file": ("frase.wav", spoken(1.0), "audio/wav")},
    )

    assert laid.status_code == 200, laid.text
    assert await _approval(client, session.id) is None


async def test_a_join_of_a_new_take_over_an_approved_draft_without_the_armed_tap_is_refused_and_nothing_is_stored(  # noqa: E501
    client, db_session, store
) -> None:
    session, _ = await _recorded(client, db_session, joined=False)
    await _approved(client, db_session, session)
    rehearsal = await _a_scene_rehearsal(db_session, session, 3)
    takes_before = await _takes(client, session.id)
    stored_before = dict(store.objects)

    refused = await _kept(client, session.id, audio=b"cena nova", part=1, origin=rehearsal.id)

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "DRAFT_APPROVED"
    assert await _takes(client, session.id) == takes_before
    assert store.objects == stored_before
    assert (await _approval(client, session.id) or {}).get("version") == 1


async def test_the_same_join_with_the_armed_tap_lands_and_re_opens_the_draft(
    client, db_session
) -> None:
    session, _ = await _recorded(client, db_session, joined=False)
    await _approved(client, db_session, session)
    rehearsal = await _a_scene_rehearsal(db_session, session, 3)

    kept = await _kept(
        client, session.id, audio=b"cena nova", part=1, origin=rehearsal.id, reopens=True
    )

    assert kept.status_code == 200, kept.text
    (landed,) = [
        one for one in await _takes(client, session.id) if one["take_id"] == kept.json()["take_id"]
    ]
    assert landed["origin"] == rehearsal.id
    assert await _approval(client, session.id) is None


async def test_a_join_that_finds_the_same_take_already_kept_brings_nothing_new_and_the_draft_stays_approved(  # noqa: E501
    client, db_session
) -> None:
    session, origins = await _recorded(client, db_session, joined=True)
    await _approved(client, db_session, session)
    (first,) = [one for one in await _takes(client, session.id) if one["ordinal"] == 1]

    again = await _kept(client, session.id, audio=b"cena 1", part=1, origin=origins[0])

    assert again.status_code == 200, again.text
    assert again.json()["take_id"] == first["take_id"]
    assert (await _approval(client, session.id) or {}).get("version") == 1
    assert await _marked(client) is True


async def test_a_whole_take_over_a_joined_recording_without_the_armed_tap_is_refused(
    client, db_session, store
) -> None:
    session, _ = await _recorded(client, db_session, joined=True)
    await _approved(client, db_session, session)
    takes_before = await _takes(client, session.id)
    stored_before = dict(store.objects)

    refused = await _kept(client, session.id, audio=b"a passagem inteira", part=None)

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "DRAFT_APPROVED"
    assert await _takes(client, session.id) == takes_before
    assert store.objects == stored_before
    assert (await _approval(client, session.id) or {}).get("version") == 1


async def test_a_whole_take_over_a_joined_recording_with_the_armed_tap_is_kept(
    client, db_session
) -> None:
    session, _ = await _recorded(client, db_session, joined=True)
    await _approved(client, db_session, session)

    kept = await _kept(client, session.id, audio=b"a passagem inteira", part=None, reopens=True)

    assert kept.status_code == 200, kept.text
    assert kept.json()["take_id"] in [one["take_id"] for one in await _takes(client, session.id)]


async def test_a_part_recorded_on_the_recording_screen_over_an_approved_draft_takes_one_tap(
    client, db_session
) -> None:
    session, _ = await _recorded(client, db_session, joined=False)
    await _approved(client, db_session, session)

    kept = await _kept(client, session.id, audio=b"a parte 1 de novo", part=1)

    assert kept.status_code == 200, kept.text
    assert await _approval(client, session.id) is None


async def test_a_whole_take_recorded_on_the_recording_screen_over_an_approved_draft_takes_one_tap(
    client, db_session
) -> None:
    session, _ = await _recorded(client, db_session, joined=False)
    await _approved(client, db_session, session)

    kept = await _kept(client, session.id, audio=b"a passagem inteira", part=None)

    assert kept.status_code == 200, kept.text
    assert kept.json()["take_id"] in [one["take_id"] for one in await _takes(client, session.id)]


async def test_a_draft_that_no_longer_stands_approved_takes_a_join_without_the_armed_tap(
    client, db_session
) -> None:
    session, _ = await _recorded(client, db_session, joined=False)
    await _approved(client, db_session, session)
    reopened = await _kept(client, session.id, audio=b"a parte 1 de novo", part=1)
    assert reopened.status_code == 200, reopened.text
    rehearsal = await _a_scene_rehearsal(db_session, session, 3)

    kept = await _kept(client, session.id, audio=b"cena nova", part=2, origin=rehearsal.id)

    assert kept.status_code == 200, kept.text


async def test_the_read_of_an_approved_draft_counts_no_outside_listeners_yet(
    client, db_session
) -> None:
    session, _ = await _recorded(client, db_session, joined=False)
    assert await _approval(client, session.id) is None
    await _approved(client, db_session, session)

    approval = await _approval(client, session.id)

    assert approval is not None
    assert approval["listeners"] == 0
