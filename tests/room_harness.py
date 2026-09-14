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
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
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

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
PART_MS = 61000
PLAYBACK_BLOCKER = "playback_did_not_cover_the_clip"

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


def the_room_speaks(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The Speaker and the synthesizer, and every line the room was asked to say.

    Kept because the answer carries a clip name and never the words: what the room actually
    said is not readable from the response at all.
    """
    said_aloud: list[str] = []

    from app.api.internalization_room import back_translation as bt_api

    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês contaram bem."

    monkeypatch.setattr(turn_module, "call_agent", speaker)

    async def voice(text: str, *_: Any, **__: Any):
        said_aloud.append(text)
        return (type("Voiced", (), {"key": f"clipe-{len(said_aloud)}"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", voice)
    return said_aloud


@asynccontextmanager
async def room_client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    """The room's routes on an app of their own, over the session the case writes through."""
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def supported_comprehension(pericope: str) -> ComprehensionState:
    return ComprehensionState(
        ledger=[
            EvidenceObservation(
                id=f"ev-{index}",
                unit_id=checkpoint.id,
                probe_id=f"probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=EvidenceResult.DEMONSTRATED,
            )
            for index, checkpoint in enumerate(checkpoints_for(pericope))
        ],
        practiced_scene_ids=scene_ids_for(pericope),
        recording_consent_given=True,
    )


def rehearsal_take(session_id: str, *, sha256: str) -> IRTake:
    return IRTake(
        session_id=session_id,
        device_id="tablet-1",
        pericope=P,
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        storage_key=f"takes/{session_id}/ensaio/{sha256}",
        size_bytes=2048,
        sha256=sha256,
        crc32c="AAAAAAA=",
        content_type="audio/mp4",
    )


async def a_rehearsed_session(db: AsyncSession) -> tuple[IRSession, IRTake]:
    """A session that has done everything a release needs except tell the passage back.

    Comprehension supported, consent given, coverage satisfied, the passage rehearsed.
    """
    session = await create_session(db, pericope=P, language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, supported_comprehension(P))
    take = rehearsal_take(session.id, sha256="a" * 64)
    db.add(take)
    await db.commit()
    return session, take


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


async def rehearsed_in_parts(db: AsyncSession, count: int) -> tuple[IRSession, list[IRTake]]:
    """A session the release refuses only for want of a report, rehearsed in `count` parts.

    Each part is its own recording with one stretch told over the whole of it, which is the
    smallest session in which the parts can be told apart at all.
    """
    session = await create_session(db, pericope=P, language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, supported_comprehension(P))

    parts = []
    for index in range(count):
        take = rehearsal_take(session.id, sha256=chr(ord("a") + index) * 64)
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


async def another_rehearsal_take(db: AsyncSession, session: IRSession, *, sha256: str) -> IRTake:
    """One more recording of the mother tongue, carrying no telling-back with it."""
    take = rehearsal_take(session.id, sha256=sha256)
    db.add(take)
    await db.commit()
    return take


async def stretch_on(db: AsyncSession, session: IRSession, take: IRTake) -> IRSegment:
    standing = await final_segments(db, session.id)
    return next(stretch for stretch in standing if stretch.take_id == take.id)


async def move_the_mother_tongue(
    db: AsyncSession, session: IRSession, part: IRTake, *, sha256: str
) -> IRTake:
    """The team recorded one part again and has told nothing back over the new audio yet.

    The first of the two calls the room's own correction is made of. The service refuses to
    carry the old explanation across when the audio moves, so what it leaves behind is a
    stretch waiting to be told.
    """
    fresh = await another_rehearsal_take(db, session, sha256=sha256)
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
