"""The listening report names the part it was played from, and the gate names what failed.

A rehearsal is recorded in parts, and the team listens to one part at a time. The report the
tablet sends says so: one entry per part, spans in that part's own milliseconds, that part's
own length. So a part recorded again loses its own listening and nothing else, and the gate
can say which parts are unheard instead of only that something is.

The flat report the older tablets send is still accepted and still stored, and it is evidence
of nothing: it says a clip was played through without saying which clip, over a passage that
was never one file. Nothing is migrated — a session in flight plays its rehearsal through
again on the new build.

These cases describe what the room decides. They do not read back how the report is stored,
except where the subject of the case is precisely that the flat numbers survive.
"""

from __future__ import annotations

import importlib
import json
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    playback_confirms_rehearsal,
)
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
    begin_back_translation_again,
    create_session,
    get_session,
    save_comprehension,
)

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
PART_MS = 61000
PLAYBACK_BLOCKER = "playback_did_not_cover_the_clip"


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> None:
    """The analyst reads the telling-back and finds nothing to raise."""
    from app.services.internalization_room import back_translation as bt_service

    async def _read(**_: Any) -> str:
        return '{"evidence_sufficient": true, "findings": []}'

    monkeypatch.setattr(bt_service, "call_agent", _read)


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Speaker and the synthesizer, so `terminei` answers without a model or a bucket."""
    from app.api.internalization_room import back_translation as bt_api

    turn_module = importlib.import_module("app.services.internalization_room.run_turn")

    async def _speak(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês contaram bem."

    monkeypatch.setattr(turn_module, "call_agent", _speak)

    async def _synthesize(text: str, *_: Any, **__: Any):
        return (type("Voiced", (), {"key": "clipe-do-veredito"})(), 0)

    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", _synthesize)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
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
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _supported_comprehension(pericope: str) -> ComprehensionState:
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


def _rehearsal_take(session_id: str, *, sha256: str) -> IRTake:
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


async def _rehearsed_in_parts(db: AsyncSession, count: int) -> tuple[IRSession, list[IRTake]]:
    """A session the release refuses only for want of a report, rehearsed in `count` parts.

    Each part is its own recording with one stretch told over the whole of it, which is the
    smallest session in which the parts can be told apart at all.
    """
    session = await create_session(db, pericope=P, language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, _supported_comprehension(P))

    parts = []
    for index in range(count):
        take = _rehearsal_take(session.id, sha256=chr(ord("a") + index) * 64)
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


async def _record_the_part_again(
    db: AsyncSession, session: IRSession, part: IRTake, *, sha256: str
) -> IRTake:
    """The team recorded one part again and told it back over the new audio.

    Two calls, which is what the room's own correction is made of: the mother tongue moves
    first and carries no telling-back with it, and the telling follows on the audio that
    replaced it.
    """
    fresh = _rehearsal_take(session.id, sha256=sha256)
    db.add(fresh)
    await db.commit()

    standing = await _stretch_on(db, session, part)
    waiting = await capture_segment(
        db, session, take_id=fresh.id, starts_ms=0, ends_ms=PART_MS, replaces=standing
    )
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


async def _told_back_on_a_new_part(db: AsyncSession, session: IRSession, *, sha256: str) -> IRTake:
    """The team started the telling-back over on a recording they made fresh."""
    take = _rehearsal_take(session.id, sha256=sha256)
    db.add(take)
    await db.commit()
    await capture_segment(
        db,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=PART_MS,
        bridge_take_id="retro-do-recomeco",
        transcript="a passagem contada de novo do comeco",
    )
    return take


async def _stretch_on(db: AsyncSession, session: IRSession, take: IRTake) -> IRSegment:
    standing = await final_segments(db, session.id)
    return next(stretch for stretch in standing if stretch.take_id == take.id)


def _covering(take: IRTake, *, duration_ms: int = PART_MS) -> dict[str, Any]:
    """What the tablet sends about a part it played through, end to end."""
    return {
        "take_id": take.id,
        "played_ranges": [[0, duration_ms]],
        "clip_duration_ms": duration_ms,
    }


async def _finish(
    client: httpx.AsyncClient, session_id: str, *, report: dict[str, Any] | None = None
) -> None:
    """Press `terminei`, with or without a report of what the tablet played."""
    answered = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/finish",
        headers={"X-Room-Key": KEY},
        **({"json": report} if report is not None else {}),
    )
    assert answered.status_code == 200, answered.text


async def _release(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    return await build_internalization_release(db, await get_session(db, session.id))


async def _blockers(db: AsyncSession, session: IRSession) -> list[str]:
    with pytest.raises(InternalizationReleaseBlocked) as refused:
        await _release(db, session)
    return refused.value.blockers


async def _stored(db: AsyncSession, session: IRSession) -> BackTranslationState:
    return back_translation_of(await get_session(db, session.id))


@pytest.mark.asyncio
async def test_four_parts_heard_confirm_and_a_replaced_part_fails_alone(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The rule, in one case: listening is kept per part, and only the part that moved is lost.

    Under the flat report the same gesture threw away the team's listening to all four parts,
    because the one number it carried was about a passage that had stopped existing.
    """
    session, (a, b, c, d) = await _rehearsed_in_parts(db_session, 4)

    await _finish(
        client,
        session.id,
        report={"played_by_take": [_covering(part) for part in (a, b, c, d)]},
    )
    heard = await _release(db_session, session)
    assert heard["readiness"] == "ready_for_refine"

    fresh_a = await _record_the_part_again(db_session, session, a, sha256="e" * 64)

    assert await _blockers(db_session, session) == [PLAYBACK_BLOCKER]
    assert playback_confirms_rehearsal(
        await _stored(db_session, session), sorted([fresh_a.id, b.id, c.id, d.id])
    ) == [fresh_a.id], "only the part the team recorded again is unheard"


@pytest.mark.asyncio
async def test_a_replaced_part_heard_again_confirms_without_the_others_replayed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Playing the new part through is enough: the other three were already heard.

    The team is working, not erring, and a rule that made them sit through the whole rehearsal
    again for one retake would be paid for in the parts they start skipping.
    """
    session, (a, b, c, d) = await _rehearsed_in_parts(db_session, 4)
    await _finish(
        client,
        session.id,
        report={"played_by_take": [_covering(part) for part in (a, b, c, d)]},
    )

    fresh_a = await _record_the_part_again(db_session, session, a, sha256="e" * 64)
    await _finish(
        client,
        session.id,
        report={"played_by_take": [_covering(part) for part in (fresh_a, b, c, d)]},
    )

    assert (await _release(db_session, session))["readiness"] == "ready_for_refine"


@pytest.mark.asyncio
async def test_an_entry_for_a_recording_the_stretches_no_longer_name_is_ignored(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """An entry about a part nobody is standing on neither confirms nor denies anything.

    It is the residue of a part that was recorded again, and it is about audio no stretch is a
    slice of any more. Refusing on it would refuse a rehearsal that was in fact heard whole;
    letting it stand in for a part it does not name is the hole this ticket closes.
    """
    session, (a, b, c, d) = await _rehearsed_in_parts(db_session, 4)
    await _finish(
        client,
        session.id,
        report={"played_by_take": [_covering(part) for part in (a, b, c, d)]},
    )

    fresh_a = await _record_the_part_again(db_session, session, a, sha256="e" * 64)
    stored = await _stored(db_session, session)

    assert playback_confirms_rehearsal(stored, sorted([fresh_a.id, b.id, c.id, d.id])) == [
        fresh_a.id
    ], "the stale entry for the old part does not stand in for the new one"
    assert playback_confirms_rehearsal(stored, sorted([b.id, c.id, d.id])) == [], (
        "a rehearsal that no longer names the part is heard on the three that remain"
    )


@pytest.mark.asyncio
async def test_a_flat_report_is_evidence_of_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The test that fails if a flat report is ever read as evidence again.

    Both halves of the same rule. A tablet on an older build sends the two numbers over the
    glued passage and the release is refused; and a row written before this change, carrying no
    per-part key at all and a server-stamped subject that names exactly the rehearsal being
    asked about, is refused too. The numbers are kept either way, because they are the record of
    what that build reported.
    """
    session, parts = await _rehearsed_in_parts(db_session, 4)
    glued = PART_MS * len(parts)
    ids = sorted(part.id for part in parts)

    await _finish(
        client,
        session.id,
        report={"played_ranges": [[0, glued]], "clip_duration_ms": glued},
    )
    stored = await _stored(db_session, session)
    in_flight = BackTranslationState.model_validate(
        {
            "scope": P,
            "played_ranges": [[0, glued]],
            "clip_duration_ms": glued,
            "played_take_ids": ids,
        }
    )

    assert await _blockers(db_session, session) == [PLAYBACK_BLOCKER]
    assert stored.played_ranges == [[0, glued]]
    assert stored.clip_duration_ms == glued
    assert stored.played_take_ids == ids
    assert playback_confirms_rehearsal(in_flight, ids) == ids, (
        "a row written before this change names every part, however the subject was stamped"
    )


def test_coverage_is_measured_per_part_with_the_tolerance() -> None:
    """750 ms of slack at each edge and between spans, per part, and never a percentage.

    The last part is Marcia's case: four minutes with twelve seconds unheard passes her 95 %
    and can hide a whole frase, which is why she argued for our absolute rule over her own.
    """
    entries = {
        "gap-of-750": ([[0, 4000], [4750, 10000]], 10000),
        "gap-of-751": ([[0, 4000], [4751, 10000]], 10000),
        "short-by-750": ([[0, 9250]], 10000),
        "short-by-751": ([[0, 9249]], 10000),
        "nothing-played": ([], 10000),
        "no-length-to-measure": ([[0, 10000]], 0),
        "four-minutes-missing-twelve-seconds": ([[0, 228000]], 240000),
    }
    state = BackTranslationState(
        played_by_take=[
            {"take_id": take_id, "played_ranges": ranges, "clip_duration_ms": duration}
            for take_id, (ranges, duration) in entries.items()
        ]
    )

    assert playback_confirms_rehearsal(state, sorted(entries)) == sorted(
        [
            "gap-of-751",
            "short-by-751",
            "nothing-played",
            "no-length-to-measure",
            "four-minutes-missing-twelve-seconds",
        ]
    )


@pytest.mark.asyncio
async def test_the_packet_carries_the_report_per_take(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """What travels to Refine is the report with a subject, and only that.

    The body carries both shapes, which is what a tablet mid-migration sends. The flat numbers
    stay in the row as the record of what was reported; the packet carries neither, because a
    consumer diffing the two versions must find them gone rather than find them unreliable.
    """
    session, parts = await _rehearsed_in_parts(db_session, 4)
    glued = PART_MS * len(parts)
    per_take = [_covering(part) for part in parts]

    await _finish(
        client,
        session.id,
        report={
            "played_by_take": per_take,
            "played_ranges": [[0, glued]],
            "clip_duration_ms": glued,
        },
    )
    packet = await _release(db_session, session)

    assert packet["schema_version"] == "tripod.internalization-release.v0.5"
    assert packet["back_translation"]["played_by_take"] == per_take
    assert "played_ranges" not in packet["back_translation"]
    assert "clip_duration_ms" not in packet["back_translation"]


@pytest.mark.asyncio
async def test_terminei_without_a_report_takes_nothing_away(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A press that carries nothing must not erase what the team already reported.

    `terminei` answers with no body at all, and it is pressed again whenever the first press
    failed after the analyst. A retry that wiped the report would cost the team the release for
    having pressed twice — and the app sends no body precisely when the clip did not run to its
    end, which is the press most likely to be repeated.
    """
    session, parts = await _rehearsed_in_parts(db_session, 4)
    per_take = [_covering(part) for part in parts]
    await _finish(client, session.id, report={"played_by_take": per_take})

    await _finish(client, session.id)

    assert (await _release(db_session, session))["back_translation"]["played_by_take"] == per_take


@pytest.mark.asyncio
async def test_a_flat_report_does_not_erase_the_parts_a_newer_build_named(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """An older build cannot take the subject away from a report that had one.

    The two builds meet on one session when a team changes tablet mid-passage. The older one
    sends the flat pair and nothing else — it cannot say what it did not measure, and silence
    about the parts is not a claim that none of them was played. Overwriting on that press
    erased a report that named every part and re-blocked a session that was ready to travel.
    """
    session, parts = await _rehearsed_in_parts(db_session, 4)
    per_take = [_covering(part) for part in parts]
    glued = PART_MS * len(parts)
    await _finish(client, session.id, report={"played_by_take": per_take})

    await _finish(
        client,
        session.id,
        report={"played_ranges": [[0, glued]], "clip_duration_ms": glued},
    )

    packet = await _release(db_session, session)
    assert packet["back_translation"]["played_by_take"] == per_take


@pytest.mark.asyncio
async def test_a_replaced_attempt_archives_the_report_per_take(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Starting over keeps what the team reported about the rehearsal they threw away.

    Read where Refine reads it. The archived attempt is the history the packet carries, and a
    report that left no trace there would make the record say the team never listened — on the
    one recording where what they heard is all that is left of it.
    """
    session, parts = await _rehearsed_in_parts(db_session, 4)
    glued = PART_MS * len(parts)
    per_take = [_covering(part) for part in parts]

    await _finish(
        client,
        session.id,
        report={
            "played_by_take": per_take,
            "played_ranges": [[0, glued]],
            "clip_duration_ms": glued,
        },
    )
    await begin_back_translation_again(db_session, session)
    started_over = await _told_back_on_a_new_part(db_session, session, sha256="e" * 64)
    await _finish(client, session.id, report={"played_by_take": [_covering(started_over)]})

    packet = await _release(db_session, session)
    archived = packet["back_translation"]["superseded_attempts"][-1]

    assert archived["played_by_take"] == per_take
    assert archived["played_ranges"] == [[0, glued]]
    assert archived["clip_duration_ms"] == glued
