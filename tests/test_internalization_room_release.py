"""The Refine handoff artifact: fail-closed gates and a closed-world package."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRTake, IRTakeKind
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Chunk,
    Finding,
    FindingKind,
    SupersededAttempt,
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
from app.services.internalization_room.sessions import (
    create_session,
    save_back_translation,
    save_comprehension,
)

P = "P03"


def _supported_comprehension(pericope: str, *, carry_one: bool = False) -> ComprehensionState:
    checkpoints = list(checkpoints_for(pericope))
    ledger = []
    for index, checkpoint in enumerate(checkpoints):
        result = (
            EvidenceResult.CARRY_TO_REFINE
            if carry_one and index == 0
            else EvidenceResult.DEMONSTRATED
        )
        ledger.append(
            EvidenceObservation(
                id=f"ev-{index}",
                unit_id=checkpoint.id,
                probe_id=f"probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=result,
            )
        )
    return ComprehensionState(
        ledger=list(ledger),
        practiced_scene_ids=scene_ids_for(pericope),
        recording_consent_given=True,
    )


def _checked_telling_back() -> BackTranslationState:
    return BackTranslationState(
        scope=P,
        chunks=[Chunk(index=1, text="Noemi voltou com Rute", starts_ms=0, ends_ms=61000)],
        findings=[],
        evidence_sufficient=True,
        checked=True,
        played_ranges=[[0, 61000]],
        clip_duration_ms=61000,
    )


def _ensaio_take(session_id: str) -> IRTake:
    return IRTake(
        session_id=session_id,
        device_id="tablet-1",
        pericope=P,
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        storage_key=f"takes/{session_id}/ensaio",
        size_bytes=2048,
        sha256="a" * 64,
        crc32c="AAAAAAA=",
        content_type="audio/mp4",
    )


async def _ready_session(db: AsyncSession, **comprehension_kwargs):
    session = await create_session(db, pericope=P, bridge_mode="guided_microchecks")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, _supported_comprehension(P, **comprehension_kwargs))
    await save_back_translation(db, session, _checked_telling_back())
    db.add(_ensaio_take(session.id))
    await db.commit()
    return session


@pytest.mark.asyncio
async def test_an_unready_session_names_every_blocker(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert set(blocked.value.blockers) >= {
        "comprehension_needs_more_work",
        "recording_consent_never_given",
        "coverage_floor_not_met",
        "no_rehearsal_audio",
        "no_telling_back",
        "telling_back_not_checked",
    }


@pytest.mark.asyncio
async def test_a_panorama_never_releases(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope="OV")

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert blocked.value.blockers == ["panorama_sessions_never_release"]


@pytest.mark.asyncio
async def test_a_ready_session_releases_a_labeled_sealed_package(
    db_session: AsyncSession,
) -> None:
    session = await _ready_session(db_session)

    artifact = await build_internalization_release(db_session, session)

    assert artifact["purpose"] == "first_team_rehearsal"
    assert artifact["readiness"] == "ready_for_refine"
    assert artifact["bridge_mode"] == "guided_microchecks"
    assert artifact["comprehension"]["outcome"] == "ready_supported"
    assert artifact["audio"]["rehearsal_takes"][0]["sha256"] == "a" * 64
    assert artifact["back_translation"]["checked"] is True
    assert artifact["back_translation"]["played_ranges"] == [[0, 61000]]
    sealed = dict(artifact)
    stamp = sealed.pop("package_sha256")
    assert len(stamp) == 64
    from app.services.internalization_room.release import _package_sha256

    assert stamp == _package_sha256(sealed)


@pytest.mark.asyncio
async def test_a_carried_point_travels_with_its_canonical_material(
    db_session: AsyncSession,
) -> None:
    session = await _ready_session(db_session, carry_one=True)

    artifact = await build_internalization_release(db_session, session)

    assert artifact["comprehension"]["outcome"] == "ready_with_open_points"
    point = artifact["comprehension"]["open_points"][0]
    assert point["reason"] == "carry_to_refine"
    assert point["checkpoint_kind"] is not None
    assert point["canonical"] is not None
    assert artifact["open_questions"] >= 1


@pytest.mark.asyncio
async def test_a_half_listened_clip_blocks_the_release(db_session: AsyncSession) -> None:
    session = await _ready_session(db_session)
    state = _checked_telling_back()
    state.played_ranges = [[0, 20000]]
    await save_back_translation(db_session, session, state)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert blocked.value.blockers == ["playback_did_not_cover_the_clip"]


@pytest.mark.asyncio
async def test_superseded_attempts_travel_clearly_marked(db_session: AsyncSession) -> None:
    session = await _ready_session(db_session)
    state = _checked_telling_back()
    state.superseded = [
        SupersededAttempt(
            chunks=[Chunk(index=1, text="tentativa antiga")],
            findings=[Finding(kind=FindingKind.MISSING, note="Orfa")],
            evidence_sufficient=False,
        )
    ]
    await save_back_translation(db_session, session, state)

    artifact = await build_internalization_release(db_session, session)

    archived = artifact["back_translation"]["superseded_attempts"][0]
    assert archived["chunks"][0]["text"] == "tentativa antiga"
    assert archived["findings"][0]["kind"] == "missing"
    assert archived["evidence_sufficient"] is False
