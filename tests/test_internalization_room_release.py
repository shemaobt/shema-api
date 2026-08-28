"""The Refine handoff artifact: fail-closed gates and a closed-world package."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
from app.services.internalization_room.back_translation import (
    BackTranslationState,
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
from app.services.internalization_room.segments import capture_segment, retire_every_segment
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


async def _one_stretch(db: AsyncSession, session: IRSession, text: str = "Noemi voltou com Rute"):
    return await capture_segment(
        db,
        session,
        take_id="ensaio-1",
        starts_ms=0,
        ends_ms=61000,
        bridge_take_id="retro-1",
        transcript=text,
    )


async def _checked_telling_back(db: AsyncSession, session: IRSession) -> BackTranslationState:
    told = await _one_stretch(db, session)
    return BackTranslationState(
        scope=P,
        findings=[],
        evidence_sufficient=True,
        checked=True,
        analysed_segment_ids=[told.id],
        played_ranges=[[0, 61000]],
        clip_duration_ms=61000,
    )


def _ensaio_take(
    session_id: str,
    *,
    scope: str = "passagem-inteira",
    pass_number: int | None = None,
    chunk_index: int | None = None,
    sha256: str = "a" * 64,
    created_at: datetime | None = None,
) -> IRTake:
    take = IRTake(
        session_id=session_id,
        device_id="tablet-1",
        pericope=P,
        kind=IRTakeKind.ENSAIO,
        scope=scope,
        pass_number=pass_number,
        chunk_index=chunk_index,
        storage_key=f"takes/{session_id}/ensaio/{sha256}",
        size_bytes=2048,
        sha256=sha256,
        crc32c="AAAAAAA=",
        content_type="audio/mp4",
    )
    if created_at is not None:
        take.created_at = created_at
    return take


async def _ready_session(db: AsyncSession, **comprehension_kwargs):
    session = await create_session(db, pericope=P, bridge_mode="guided_microchecks")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, _supported_comprehension(P, **comprehension_kwargs))
    await save_back_translation(db, session, await _checked_telling_back(db, session))
    db.add(_ensaio_take(session.id))
    await db.commit()
    return session


@pytest.mark.asyncio
async def test_an_unready_session_names_every_blocker(db_session: AsyncSession) -> None:
    """`telling_back_not_checked` left this list with ENG-584: a telling-back has to exist,
    which `no_telling_back` already says, but it does not have to have come out clean."""
    session = await create_session(db_session, pericope=P)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert set(blocked.value.blockers) >= {
        "comprehension_needs_more_work",
        "recording_consent_never_given",
        "coverage_floor_not_met",
        "no_rehearsal_audio",
        "no_telling_back",
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
    state = await _checked_telling_back(db_session, session)
    state.played_ranges = [[0, 20000]]
    await save_back_translation(db_session, session, state)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert blocked.value.blockers == ["playback_did_not_cover_the_clip"]


@pytest.mark.asyncio
async def test_a_listening_report_that_cannot_be_about_this_clip_blocks_the_release(
    db_session: AsyncSession,
) -> None:
    """The shape the partial replacement creates: a shorter clip under an older report.

    The report is complete and coherent about *something* — it just cannot be about the
    61-second stretch it is filed against, because the clip is 37 seconds long. The
    package that carries it must not travel.
    """
    session = await _ready_session(db_session)
    state = await _checked_telling_back(db_session, session)
    state.clip_duration_ms = 37000
    await save_back_translation(db_session, session, state)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert blocked.value.blockers == ["playback_did_not_cover_the_clip"]


@pytest.mark.asyncio
async def test_superseded_attempts_travel_clearly_marked(db_session: AsyncSession) -> None:
    session = await _ready_session(db_session)
    state = await _checked_telling_back(db_session, session)
    state.superseded = [
        SupersededAttempt(
            findings=[Finding(kind=FindingKind.MISSING, note="Orfa")],
            evidence_sufficient=False,
        )
    ]
    await save_back_translation(db_session, session, state)
    await retire_every_segment(db_session, session.id)
    abandoned = await _one_stretch(db_session, session, "tentativa antiga")
    await retire_every_segment(db_session, session.id)
    kept = await _one_stretch(db_session, session)

    artifact = await build_internalization_release(db_session, session)

    archived = artifact["back_translation"]["superseded_attempts"][0]
    assert archived["findings"][0]["kind"] == "missing"
    assert archived["evidence_sufficient"] is False
    replaced = artifact["back_translation"]["superseded_segments"]
    assert abandoned.id in [one["segment_id"] for one in replaced]
    assert "tentativa antiga" in [one["text"] for one in replaced], (
        "o que a equipe contou e depois refez continua viajando, marcado como não valendo mais"
    )
    assert [one["segment_id"] for one in artifact["back_translation"]["segments"]] == [kept.id]


@pytest.mark.asyncio
async def test_the_rehearsal_they_replaced_is_told_apart_from_the_one_they_kept(
    db_session: AsyncSession,
) -> None:
    """A re-record starts the parts at one again, so the rehearsal the team abandoned and
    the one they kept both reach here as `parte-1`, chunk 1, and the audio is addressed by
    its own hash, so both rows stay.

    The pass is the only label that separates them, and the order has to come from it: the
    tablet's outbox drains whenever the link comes back, so the abandoned take can be
    written down after the take that replaced it.

    The whole-passage take `_ready_session` leaves carries neither a chunk nor a pass, and
    it is read here too: it comes first on every engine now that `takes_of` says where a
    NULL belongs, which is the same reading order — the undivided recording before the
    parts, and a take from before the room sent a pass before the ones that carry it.
    """
    session = await _ready_session(db_session)
    db_session.add(
        _ensaio_take(
            session.id,
            scope="parte-1",
            pass_number=2,
            chunk_index=1,
            sha256="c" * 64,
            created_at=datetime(2026, 8, 23, 9, 0, tzinfo=UTC),
        )
    )
    db_session.add(
        _ensaio_take(
            session.id,
            scope="parte-1",
            pass_number=1,
            chunk_index=1,
            sha256="b" * 64,
            created_at=datetime(2026, 8, 23, 10, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()

    artifact = await build_internalization_release(db_session, session)

    seen = [
        (take["chunk_index"], take["pass_number"], take["sha256"])
        for take in artifact["audio"]["rehearsal_takes"]
    ]

    assert seen == [(None, None, "a" * 64), (1, 1, "b" * 64), (1, 2, "c" * 64)], (
        "sem a passada, quem abrisse a passagem no Refine ouvia o ensaio abandonado como "
        "o primeiro da equipe, e pela chegada a ordem sairia trocada"
    )


async def _told_back_with_an_open_finding(
    db: AsyncSession, session: IRSession
) -> BackTranslationState:
    """A telling-back the team finished and chose not to resolve.

    `analysed_segment_ids` names the stretch because the analyst did read it — that is what
    makes the finding open rather than the verdict unasked.

    `checked` is written as `finding is None and evidence_sufficient`, so an open finding
    makes it false — which is the whole state this slice is about.
    """
    told = await _one_stretch(db, session)
    return BackTranslationState(
        scope=P,
        findings=[
            Finding(
                kind=FindingKind.MEANING_CHANGE,
                note="a equipe disse que Noemi voltou alegre",
                segment_id=told.id,
            )
        ],
        evidence_sufficient=True,
        checked=False,
        analysed_segment_ids=[told.id],
        played_ranges=[[0, 61000]],
        clip_duration_ms=61000,
    )


@pytest.mark.asyncio
async def test_a_session_carrying_an_open_finding_still_releases(
    db_session: AsyncSession,
) -> None:
    """Taking the questions to Refine is an outcome the room is meant to have.

    Refusing it left the rehearsal, the coverage, the ledger and the telling-back on the
    tablet with no way out, for a team that had done every piece of the work.
    """
    session = await _ready_session(db_session)
    await save_back_translation(
        db_session, session, await _told_back_with_an_open_finding(db_session, session)
    )

    artifact = await build_internalization_release(db_session, session)

    assert artifact["readiness"] == "ready_for_refine"
    assert artifact["back_translation"]["checked"] is False


@pytest.mark.asyncio
async def test_a_session_that_never_told_anything_back_is_still_refused(
    db_session: AsyncSession,
) -> None:
    """The door that has to stay shut: nothing was told back at all."""
    session = await _ready_session(db_session)
    await save_back_translation(db_session, session, BackTranslationState(scope=P))
    await retire_every_segment(db_session, session.id)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert "no_telling_back" in blocked.value.blockers


@pytest.mark.asyncio
async def test_a_checked_session_releases_exactly_as_before(db_session: AsyncSession) -> None:
    session = await _ready_session(db_session)

    artifact = await build_internalization_release(db_session, session)

    assert artifact["readiness"] == "ready_for_refine"
    assert artifact["back_translation"]["checked"] is True
    assert artifact["back_translation"]["findings"] == []


@pytest.mark.asyncio
async def test_the_finding_travels_in_the_package_it_unblocked(
    db_session: AsyncSession,
) -> None:
    """A package that does not name the finding is worse than the refusal.

    The team would have carried the question all the way to Refine and nobody there would
    see it — and unlike a blocked release, that looks resolved.
    """
    session = await _ready_session(db_session)
    await save_back_translation(
        db_session, session, await _told_back_with_an_open_finding(db_session, session)
    )

    artifact = await build_internalization_release(db_session, session)

    carried = artifact["back_translation"]["findings"]
    assert [finding["kind"] for finding in carried] == ["meaning_change"]
    assert carried[0]["note"] == "a equipe disse que Noemi voltou alegre"
    assert carried[0]["segment_id"] is not None


@pytest.mark.asyncio
async def test_the_other_doors_are_still_shut(db_session: AsyncSession) -> None:
    """One item leaves the list; its neighbours are not loosened with it."""
    session = await _ready_session(db_session)
    await save_back_translation(
        db_session, session, await _told_back_with_an_open_finding(db_session, session)
    )
    session.bridge_mode = "calibration_pending"
    await save_comprehension(db_session, session, ComprehensionState())
    session.coverage_state = {}
    await db_session.commit()

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert set(blocked.value.blockers) >= {
        "bridge_language_never_calibrated",
        "comprehension_needs_more_work",
        "recording_consent_never_given",
        "coverage_floor_not_met",
    }


@pytest.mark.asyncio
async def test_a_telling_back_nobody_read_does_not_leave_looking_clean(
    db_session: AsyncSession,
) -> None:
    """Carrying the questions is the point; carrying silence as if it were clean is not.

    A team that captured the stretches and never pressed `terminei` has an unread
    telling-back, and its defaults — no findings, evidence sufficient — are the same
    package a clean check produces.
    """
    session = await _ready_session(db_session)
    await save_back_translation(
        db_session,
        session,
        BackTranslationState(scope=P),
    )
    await _one_stretch(db_session, session)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert "telling_back_never_analysed" in blocked.value.blockers
