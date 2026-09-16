"""The room a back-translation case stands in, and the doubles it presses `terminei` through.

A session rehearsed in parts, told back, and pressed on over HTTP is the same scaffold in
every case about the telling-back: the cases differ in what the team played and in what the
room is then expected to answer. Built here once so a case reads as the decision it is about.

Fixtures are not exported. A fixture imported into a test module and then named as a test
parameter is a redefinition the lint refuses (F811), so what travels is the builder and each
module keeps the three-line fixture that calls it — which is also how `release_harness` and
`alembic_harness` are used.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    build_internalization_release,
)
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import (
    back_translation_of,
    create_session,
    get_session,
    save_comprehension,
)
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import (
    KEY,
    PREFIX,
    TABLET,
    P,
    ensaio_take,
    supported_comprehension,
)

PART_MS = 61000
PLAYBACK_BLOCKER = "playback_did_not_cover_the_clip"

#: When the parts of a built rehearsal were recorded. Explicit and in the past, because the
#: newest take under a part's number is that part and SQLite stamps `now()` to the second: a
#: part uploaded during the case has to be newer than the one it was recorded over, and two
#: rows written in the same second cannot say which.
REHEARSED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

#: The heading that only the correction prompt carries. The double tells the two readings
#: apart by it, the way a reader would — not by counting calls.
CORRECTION_MARK = "## What the team told back now"


class Analyst:
    """The analyst, and a count of how many times it was actually asked to read.

    A refusal has to be answered before the reading, and "did not run" is not readable from
    the answer alone: a clean reading and no reading at all agree on every field but this
    counter.
    """

    def __init__(self) -> None:
        self.readings = 0

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        self.readings += 1
        return '{"evidence_sufficient": true, "findings": []}'


def the_analyst_reads(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    """Put a counting analyst in place of the one that costs a model call."""
    from app.services.internalization_room import back_translation as bt_service

    reader = Analyst()
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


def the_bucket_is_in_memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    """Keep the takes where a case can reach them, so a route that stores audio needs no bucket.

    The store the hard-stretch cases already use; a second one here would be a second answer
    to what a bucket does.
    """
    from app.services.internalization_room import takes as takes_service

    store = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: store)
    return store


def the_transcriber_says(monkeypatch: pytest.MonkeyPatch, said: list[str]) -> None:
    """What the transcriber will answer, one entry per capture, in the order they are sent."""
    from app.api.internalization_room import back_translation as bt_api

    async def heard(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    monkeypatch.setattr(bt_api, "heard", heard)


def the_room_speaks(
    monkeypatch: pytest.MonkeyPatch, *, briefs: list[str] | None = None
) -> list[str]:
    """The Speaker and the synthesizer, and every line the room was asked to say.

    Kept because the answer carries a clip name and never the words: what the room actually
    said is not readable from the response at all.

    `briefs` collects what the Speaker was told, for a case whose subject is the instruction
    the room ordered rather than the words that came back. The Validator's own brief is not
    one of them — it is judging a draft, not being told how to end a turn — and it is told
    apart here by the field it is asked to answer with.
    """
    said_aloud: list[str] = []

    from app.api.internalization_room import back_translation as bt_api

    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        if briefs is not None:
            briefs.append(system_prompt)
        return "Vocês contaram bem."

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def voice(text: str, *_: Any, **__: Any):
        said_aloud.append(text)
        return (type("Voiced", (), {"key": f"clipe-{len(said_aloud)}"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", voice)
    return said_aloud


@asynccontextmanager
async def room_client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, *, runner_key: str | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    """The room's routes on an app of their own, over the session the case writes through.

    `runner_key` opens the text seam as well, which exists only where the key is set, and
    sends it on every request the way her runner does.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    if runner_key is not None:
        monkeypatch.setattr(
            get_settings(), "internalization_room_runner_key", runner_key, raising=False
        )

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Access-Code": runner_key} if runner_key else {},
    ) as client:
        yield client


async def tell_back_about(
    db: AsyncSession,
    session: IRSession,
    take: IRTake,
    *,
    transcript: str = "Noemi voltou com Rute",
    bridge_take_id: str = "retro-1",
) -> IRSegment:
    return await capture_segment(
        db,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=PART_MS,
        bridge_take_id=bridge_take_id,
        transcript=transcript,
    )


async def rehearsed_in_parts(
    db: AsyncSession, count: int, *, project_id: str | None = None
) -> tuple[IRSession, list[IRTake]]:
    """A session the release refuses only for want of a report, rehearsed in `count` parts.

    Each part is its own recording with one stretch told over the whole of it, which is the
    smallest session in which the parts can be told apart at all.

    `project_id` is the team whose conversation this is, named only by the cases that reach a
    facilitator route: those resolve the session by the team that owns it, and one naming no
    project is refused before anything about the listening is read.

    The parts are numbered the way the tablet numbers them — `parte-N` and `chunk_index` N,
    from one — because a part's identity is that number and not the scope string. Unnumbered,
    every part of a built rehearsal was one part under the same null.
    """
    session = await create_session(db, pericope=P, project_id=project_id, language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, supported_comprehension(P))

    parts = []
    for index in range(count):
        take = ensaio_take(
            session.id,
            scope=f"parte-{index + 1}",
            ordinal=index + 1,
            sha256=chr(ord("a") + index) * 64,
            created_at=REHEARSED_AT + timedelta(minutes=index),
            project_id=session.project_id,
        )
        db.add(take)
        await db.commit()
        await capture_segment(
            db,
            session,
            take_id=take.id,
            starts_ms=0,
            ends_ms=PART_MS,
            bridge_take_id=f"retro-{index}",
            transcript=f"parte {index} contada de volta",
        )
        parts.append(take)
    return session, parts


async def another_rehearsal_take(
    db: AsyncSession,
    session: IRSession,
    *,
    sha256: str,
    scope: str = "passagem-inteira",
    ordinal: int | None = None,
    created_at: datetime | None = None,
) -> IRTake:
    """One more recording of the mother tongue, carrying no telling-back with it."""
    take = ensaio_take(
        session.id,
        scope=scope,
        ordinal=ordinal,
        sha256=sha256,
        created_at=created_at,
        project_id=session.project_id,
    )
    db.add(take)
    await db.commit()
    return take


async def stretch_on(db: AsyncSession, session: IRSession, take: IRTake) -> IRSegment:
    standing = await final_segments(db, session.id)
    return next(stretch for stretch in standing if stretch.take_id == take.id)


def _after(take: IRTake) -> datetime | None:
    """A moment past a take's own, so which of two takes is the newer never rests on a clock."""
    return take.created_at + timedelta(minutes=1) if take.created_at else None


async def move_the_mother_tongue(
    db: AsyncSession, session: IRSession, part: IRTake, *, sha256: str
) -> IRTake:
    """The team recorded one part again and has told nothing back over the new audio yet.

    The first of the two calls the room's own correction is made of. The service refuses to
    carry the old explanation across when the audio moves, so what it leaves behind is a
    stretch waiting to be told.

    The fresh recording takes the replaced part's place — its scope and its number — the way a
    **Rebuild** takes the placement of the recording it was built from. A part recorded again
    is the same part, and a take that landed with no number would be a part of its own.
    """
    fresh = await another_rehearsal_take(
        db,
        session,
        sha256=sha256,
        scope=part.scope,
        ordinal=part.ordinal,
        created_at=_after(part),
    )
    standing = await stretch_on(db, session, part)
    await capture_segment(
        db, session, take_id=fresh.id, starts_ms=0, ends_ms=PART_MS, replaces=standing
    )
    return fresh


async def record_the_part_again(
    db: AsyncSession, session: IRSession, part: IRTake, *, sha256: str
) -> IRTake:
    """The team recorded one part again and told it back over the new audio.

    The second of the two calls: the telling follows on the audio that replaced the old one.
    """
    fresh = await move_the_mother_tongue(db, session, part, sha256=sha256)
    waiting = await stretch_on(db, session, fresh)
    await capture_segment(
        db,
        session,
        take_id=fresh.id,
        starts_ms=0,
        ends_ms=PART_MS,
        bridge_take_id="retro-de-novo",
        transcript="a parte recontada",
        replaces=waiting,
    )
    return fresh


def played_every_part(
    take_ids: Iterable[str],
    *,
    played_ranges: list[list[int]] | None = None,
    duration_ms: int = PART_MS,
) -> dict[str, Any]:
    """The body of a `terminei` that names each part and what the tablet played of it.

    One entry per part, in that part's own milliseconds. The defaults describe a part played
    through; a case about a report that falls short says so by naming the numbers it means.
    """
    spans = [[0, duration_ms]] if played_ranges is None else played_ranges
    return {
        "played_by_take": [
            {"take_id": take_id, "played_ranges": spans, "clip_duration_ms": duration_ms}
            for take_id in sorted(take_ids)
        ]
    }


async def heard_every_part(
    db: AsyncSession,
    session_id: str,
    *,
    played_ranges: list[list[int]] | None = None,
    duration_ms: int = PART_MS,
) -> dict[str, Any]:
    """The same, over the parts the session's stretches are standing on right now."""
    told = await final_segments(db, session_id)
    return played_every_part(
        {stretch.take_id for stretch in told}, played_ranges=played_ranges, duration_ms=duration_ms
    )


async def upload_a_part(
    client: httpx.AsyncClient, session_id: str, *, part: int | None, audio: bytes
) -> httpx.Response:
    """Send a rehearsal recording up the way the tablet sends one.

    `part` is the number the app puts on it — the `parte-N` scope and the `chunk_index` beside
    it — and `None` is the rehearsal told whole, which the app sends with neither. The verb for
    *this part was recorded again* is implicit in this call and lives nowhere else, so a case
    about it has to arrive through this door and not by writing the row.
    """
    data = {
        "kind": "ensaio",
        "scope": "passagem-inteira" if part is None else f"parte-{part}",
    }
    if part is not None:
        data["chunk_index"] = str(part)
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers={"X-Room-Key": KEY, "X-Room-Device": TABLET},
        data=data,
        files={"file": ("gravacao.m4a", audio, "audio/mp4")},
    )


async def press_terminei(
    client: httpx.AsyncClient, session_id: str, *, report: dict[str, Any] | None = None
) -> httpx.Response:
    """Press `terminei`, with or without a report of what the tablet played."""
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish",
        headers={"X-Room-Key": KEY},
        **({"json": report} if report is not None else {}),
    )


async def release_packet(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    return await build_internalization_release(db, await get_session(db, session.id))


async def release_blockers(db: AsyncSession, session: IRSession) -> list[str]:
    with pytest.raises(InternalizationReleaseBlocked) as refused:
        await release_packet(db, session)
    return refused.value.blockers


async def stored_telling_back(db: AsyncSession, session: IRSession) -> BackTranslationState:
    return back_translation_of(await get_session(db, session.id))
