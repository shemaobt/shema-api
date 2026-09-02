"""The release refuses a package whose playback report is not about the rehearsal it ships.

The report of playback is the room's only evidence that the team heard their own recording
before the telling-back was blessed. Evidence about a clip that is no longer in play, or no
evidence at all, is not evidence — and a package that travels on it says downstream that a
team listened when nobody knows whether they did.

These cases describe what the room decides: the release is built, or it is refused naming a
blocker. None of them reads back how the report is stored.
"""

from __future__ import annotations

import importlib
import json
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
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
    begin_back_translation_again,
    create_session,
    get_session,
    save_comprehension,
)

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
CLIP_MS = 61000
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


async def _rehearsed(db: AsyncSession) -> tuple[IRSession, IRTake]:
    """A session that has done everything a release needs except tell the passage back.

    Comprehension supported, consent given, coverage satisfied, the passage rehearsed.
    """
    session = await create_session(db, pericope=P, bridge_mode="guided_microchecks", language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, _supported_comprehension(P))
    take = _rehearsal_take(session.id, sha256="a" * 64)
    db.add(take)
    await db.commit()
    return session, take


async def _tell_back_about(db: AsyncSession, session: IRSession, take: IRTake) -> None:
    await capture_segment(
        db,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id="retro-1",
        transcript="Noemi voltou com Rute",
    )


async def _rehearsed_and_told_back(db: AsyncSession) -> IRSession:
    """The same, with one stretch of the rehearsal explained. Only the report is missing."""
    session, take = await _rehearsed(db)
    await _tell_back_about(db, session, take)
    return session


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


async def _re_record_the_rehearsal(db: AsyncSession, session: IRSession) -> IRTake:
    """The team threw the clip away and recorded the passage again."""
    take = _rehearsal_take(session.id, sha256="b" * 64)
    db.add(take)
    await db.commit()
    return take


async def _release(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    return await build_internalization_release(db, await get_session(db, session.id))


async def _blockers(db: AsyncSession, session: IRSession) -> list[str]:
    with pytest.raises(InternalizationReleaseBlocked) as refused:
        await _release(db, session)
    return refused.value.blockers


@pytest.mark.asyncio
async def test_a_release_with_no_report_of_playback_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 1. The tablet says nothing about playback, which is what it says whenever the
    clip did not run to its end. Silence is not a claim that the team heard themselves."""
    session = await _rehearsed_and_told_back(db_session)

    await _finish(client, session.id)

    assert await _blockers(db_session, session) == [PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_a_report_about_a_rehearsal_the_team_re_recorded_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 2. The report was honest about the clip it was made of, and that clip is gone.

    Starting the telling-back over is what a re-record does, and it takes the report with it,
    so what reaches the gate is a session that told the new clip back and never said anybody
    played it. The package would otherwise travel on a report about audio nobody will hear.
    """
    session = await _rehearsed_and_told_back(db_session)
    await _finish(
        client, session.id, report={"played_ranges": [[0, CLIP_MS]], "clip_duration_ms": CLIP_MS}
    )

    again = await _re_record_the_rehearsal(db_session, session)
    await begin_back_translation_again(db_session, session)
    await _tell_back_about(db_session, session, again)
    await _finish(client, session.id)

    assert await _blockers(db_session, session) == [PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_a_report_does_not_survive_the_audio_under_it_being_replaced(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 2, reaching it by the other road, and the one the fix is named after.

    The team keeps the telling-back and re-records the mother-tongue audio under one stretch.
    Nothing clears the report — it is still there, still complete — but the stretch is now a
    slice of a recording that did not exist when the team pressed play. What it says they
    heard and what the package carries have come apart, which is the comparison this gate
    exists to make; a case where the report is merely absent never reaches it.

    The stretch is told again over the audio that replaced it, which is the second call the
    room's own correction is made of. That leaves the session otherwise releasable, so the stale
    report is the only thing standing in its way.
    """
    session = await _rehearsed_and_told_back(db_session)
    await _finish(
        client, session.id, report={"played_ranges": [[0, CLIP_MS]], "clip_duration_ms": CLIP_MS}
    )

    again = await _re_record_the_rehearsal(db_session, session)
    standing = (await final_segments(db_session, session.id))[0]
    waiting = await capture_segment(
        db_session,
        session,
        take_id=again.id,
        starts_ms=0,
        ends_ms=CLIP_MS,
        replaces=standing,
    )
    await capture_segment(
        db_session,
        session,
        take_id=again.id,
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id="retro-novo",
        transcript="Rute disse que ia junto",
        replaces=waiting,
    )

    assert await _blockers(db_session, session) == [PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_an_honest_report_on_the_current_rehearsal_releases(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 3. Control: the team played their own clip through, and the package travels."""
    session = await _rehearsed_and_told_back(db_session)

    await _finish(
        client, session.id, report={"played_ranges": [[0, CLIP_MS]], "clip_duration_ms": CLIP_MS}
    )

    artifact = await _release(db_session, session)
    assert artifact["readiness"] == "ready_for_refine"


@pytest.mark.asyncio
async def test_a_fresh_report_after_a_re_record_releases(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 3 after a detour. Control: re-recording is the team working, not the team erring,
    and playing the new clip through has to be enough to release it."""
    session = await _rehearsed_and_told_back(db_session)
    await _finish(
        client, session.id, report={"played_ranges": [[0, CLIP_MS]], "clip_duration_ms": CLIP_MS}
    )

    again = await _re_record_the_rehearsal(db_session, session)
    await begin_back_translation_again(db_session, session)
    await _tell_back_about(db_session, session, again)
    await _finish(
        client, session.id, report={"played_ranges": [[0, CLIP_MS]], "clip_duration_ms": CLIP_MS}
    )

    artifact = await _release(db_session, session)
    assert artifact["readiness"] == "ready_for_refine"


@pytest.mark.asyncio
async def test_a_report_that_does_not_reach_the_end_of_its_clip_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 4. Control against regression: half a clip played is still half a clip played."""
    session = await _rehearsed_and_told_back(db_session)

    await _finish(
        client, session.id, report={"played_ranges": [[0, 20000]], "clip_duration_ms": CLIP_MS}
    )

    assert await _blockers(db_session, session) == [PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_a_report_with_no_clip_to_measure_against_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Stretches played, but no clip length to compare them to, so nothing can be checked.

    The request model lets either number arrive alone. Neither alone is proof: this half
    cannot be measured, and the other half — a length with nothing played — is a report that
    the team played nothing at all.
    """
    session = await _rehearsed_and_told_back(db_session)

    await _finish(client, session.id, report={"played_ranges": [[0, CLIP_MS]]})

    assert await _blockers(db_session, session) == [PLAYBACK_BLOCKER]


@pytest.mark.asyncio
async def test_a_session_with_nothing_told_back_is_not_also_blamed_for_playback(
    db_session: AsyncSession,
) -> None:
    """One thing wrong is told to the team once.

    There is nothing to have played back before a stretch exists, so the room names what is
    actually missing and does not hand the team a second errand that would not help.
    """
    session, _ = await _rehearsed(db_session)

    refused = await _blockers(db_session, session)

    assert "no_telling_back" in refused
    assert PLAYBACK_BLOCKER not in refused
