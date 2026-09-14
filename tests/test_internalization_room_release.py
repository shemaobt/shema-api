"""The Refine handoff artifact: fail-closed gates and a closed-world package."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import release as release_module
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
    SupersededAttempt,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.release import (
    FORCEABLE_BLOCKERS,
    InternalizationReleaseBlocked,
    approve_release,
    build_internalization_release,
)
from app.services.internalization_room.segments import (
    capture_segment,
    divide_segment,
    final_segments,
    retire_every_segment,
)
from app.services.internalization_room.sessions import (
    create_session,
    save_back_translation,
    save_comprehension,
)
from tests.release_harness import (
    P,
    checked_telling_back,
    ensaio_take,
    one_stretch,
    ready_session,
    reported_playback,
    retro_take,
)


@pytest.mark.asyncio
async def test_an_unready_session_names_every_blocker(db_session: AsyncSession) -> None:
    """`telling_back_not_checked` left this list with ENG-584 and came back with ENG-882: a
    telling-back has to exist, which `no_telling_back` already says, and it has to have come
    out clean, which is Marcia's gate and only a facilitator's code sets aside."""
    session = await create_session(db_session, pericope=P)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert set(blocked.value.blockers) >= {
        "comprehension_needs_more_work",
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
    session = await ready_session(db_session)

    artifact = await build_internalization_release(db_session, session)

    assert artifact["purpose"] == "first_team_rehearsal"
    assert artifact["readiness"] == "ready_for_refine"
    assert artifact["comprehension"]["outcome"] == "ready_supported"
    assert artifact["audio"]["rehearsal_takes"][0]["sha256"] == "a" * 64
    assert artifact["back_translation"]["checked"] is True
    assert [entry["played_ranges"] for entry in artifact["back_translation"]["played_by_take"]] == [
        [[0, 61000]]
    ]
    sealed = dict(artifact)
    stamp = sealed.pop("package_sha256")
    sealed.pop("created_at")
    sealed.pop("release_id")
    sealed.pop("version")
    assert len(stamp) == 64
    from app.services.internalization_room.release import _package_sha256

    assert stamp == _package_sha256(sealed)


class _FixedClock:
    """A stand-in for the module's ``datetime``, answering ``now`` from a fixed queue."""

    def __init__(self, instants: list[datetime]) -> None:
        self._instants = list(instants)

    def now(self, tz=None):
        return self._instants.pop(0)


@pytest.mark.asyncio
async def test_two_reads_of_one_session_carry_one_hash_and_two_clocks(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await ready_session(db_session)
    first_instant = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    second_instant = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
    monkeypatch.setattr(release_module, "datetime", _FixedClock([first_instant, second_instant]))

    first = await build_internalization_release(db_session, session)
    second = await build_internalization_release(db_session, session)

    assert first["created_at"] == first_instant.isoformat()
    assert second["created_at"] == second_instant.isoformat()
    assert first["package_sha256"] == second["package_sha256"], (
        "duas leituras da mesma sessão não mudaram nada além do relógio de exportação"
    )


@pytest.mark.asyncio
async def test_one_more_stretch_told_changes_the_packet_hash(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await ready_session(db_session)
    frozen = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    monkeypatch.setattr(release_module, "datetime", _FixedClock([frozen, frozen]))

    before = await build_internalization_release(db_session, session)
    await one_stretch(db_session, session, text="Rute espigou no campo de Boaz")
    after = await build_internalization_release(db_session, session)

    assert before["package_sha256"] != after["package_sha256"], (
        "o mesmo relógio nas duas leituras não pode esconder que o conteúdo mudou"
    )


@pytest.mark.asyncio
async def test_a_carried_point_travels_with_its_canonical_material(
    db_session: AsyncSession,
) -> None:
    session = await ready_session(db_session, carry_one=True)

    artifact = await build_internalization_release(db_session, session)

    assert artifact["comprehension"]["outcome"] == "ready_with_open_points"
    point = artifact["comprehension"]["open_points"][0]
    assert point["reason"] == "carry_to_refine"
    assert point["checkpoint_kind"] is not None
    assert point["canonical"] is not None
    assert artifact["open_questions"] >= 1


@pytest.mark.asyncio
async def test_a_half_listened_clip_blocks_the_release(db_session: AsyncSession) -> None:
    session = await ready_session(db_session)
    state = await checked_telling_back(db_session, session)
    await reported_playback(db_session, session, state, played_ranges=[[0, 20000]])

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
    session = await ready_session(db_session)
    state = await checked_telling_back(db_session, session)
    await reported_playback(db_session, session, state, clip_duration_ms=37000)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert blocked.value.blockers == ["playback_did_not_cover_the_clip"]


@pytest.mark.asyncio
async def test_superseded_attempts_travel_clearly_marked(db_session: AsyncSession) -> None:
    session = await ready_session(db_session)
    state = await checked_telling_back(db_session, session)
    state.superseded = [
        SupersededAttempt(findings=[Finding(kind=FindingKind.MISSING, note="Orfa")])
    ]
    await reported_playback(db_session, session, state)
    await retire_every_segment(db_session, session.id)
    abandoned = await one_stretch(db_session, session, "tentativa antiga")
    await retire_every_segment(db_session, session.id)
    kept = await one_stretch(db_session, session)

    artifact = await build_internalization_release(db_session, session)

    archived = artifact["back_translation"]["superseded_attempts"][0]
    assert archived["findings"][0]["kind"] == "missing"
    assert "evidence_sufficient" not in archived
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

    The whole-passage take `ready_session` leaves carries neither an ordinal nor a pass, and
    it is read here too: it comes first on every engine now that `takes_of` says where a
    NULL belongs, which is the same reading order — the undivided recording before the
    parts, and a take from before the room sent a pass before the ones that carry it.
    """
    session = await ready_session(db_session)
    db_session.add(
        ensaio_take(
            session.id,
            scope="parte-1",
            pass_number=2,
            ordinal=1,
            sha256="c" * 64,
            created_at=datetime(2026, 8, 23, 9, 0, tzinfo=UTC),
        )
    )
    db_session.add(
        ensaio_take(
            session.id,
            scope="parte-1",
            pass_number=1,
            ordinal=1,
            sha256="b" * 64,
            created_at=datetime(2026, 8, 23, 10, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()

    artifact = await build_internalization_release(db_session, session)

    seen = [
        (take["ordinal"], take["pass_number"], take["sha256"])
        for take in artifact["audio"]["rehearsal_takes"]
    ]

    assert seen == [(None, None, "a" * 64), (1, 1, "b" * 64), (1, 2, "c" * 64)], (
        "sem a passada, quem abrisse a passagem no Refine ouvia o ensaio abandonado como "
        "o primeiro da equipe, e pela chegada a ordem sairia trocada"
    )


@pytest.mark.asyncio
async def test_ordinal_less_retro_takes_are_listed_by_pass_then_by_creation(
    db_session: AsyncSession,
) -> None:
    session = await ready_session(db_session)
    told_last = retro_take(
        session.id,
        pass_number=2,
        sha256="d" * 64,
        created_at=datetime(2026, 8, 23, 9, 0, tzinfo=UTC),
    )
    told_first = retro_take(
        session.id,
        pass_number=1,
        sha256="e" * 64,
        created_at=datetime(2026, 8, 23, 10, 0, tzinfo=UTC),
    )
    told_second = retro_take(
        session.id,
        pass_number=1,
        sha256="f" * 64,
        created_at=datetime(2026, 8, 23, 11, 0, tzinfo=UTC),
    )
    db_session.add_all([told_last, told_first, told_second])
    await db_session.commit()

    artifact = await build_internalization_release(db_session, session)

    retro_takes = artifact["back_translation"]["retro_takes"]
    assert [take["take_id"] for take in retro_takes] == [
        told_first.id,
        told_second.id,
        told_last.id,
    ], "sem ordinal, o pacote lista pela passada e depois pela chegada"


async def _told_back_with_an_open_finding(
    db: AsyncSession, session: IRSession
) -> BackTranslationState:
    """A telling-back the team finished and chose not to resolve.

    `analysed_segment_ids` names the stretch because the analyst did read it — that is what
    makes the finding open rather than the verdict unasked.

    `checked` is written as `finding is None`, so an open finding makes it false — which is
    the whole state this slice is about.
    """
    told = await one_stretch(db, session)
    return BackTranslationState(
        scope=P,
        findings=[
            Finding(
                kind=FindingKind.ADDITION,
                note="a equipe disse que Noemi voltou alegre",
                segment_id=told.id,
                chunk=1,
            )
        ],
        checked=False,
        analysed_segment_ids=[told.id],
    )


@pytest.mark.asyncio
async def test_a_session_carrying_an_open_finding_is_refused(
    db_session: AsyncSession,
) -> None:
    """ENG-584 argued the other way here, and the argument lost.

    It was that taking the questions to Refine is an outcome the room is meant to have, and
    that refusing it left a team who had done every piece of the work with no way out. What
    it did not weigh is what a disputed finding actually is: the map wrong, which is rare and
    worth having; the team not understanding; the recogniser erring. Only the first deserves
    to travel, and a door open to all three sends the other two downstream as a passage the
    room approved — heard as approved at the community's check.

    The way out is still there and it is a person's: the raised hand, answered, and then the
    facilitator's code.
    """
    session = await ready_session(db_session)
    await reported_playback(
        db_session, session, await _told_back_with_an_open_finding(db_session, session)
    )

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert blocked.value.blockers == ["telling_back_not_checked"]


@pytest.mark.asyncio
async def test_a_never_analysed_telling_back_is_named_before_the_open_finding(
    db_session: AsyncSession,
) -> None:
    """One errand at a time, and this is the one that comes first.

    A telling-back nobody read has no finding to be open: its emptiness is the default, not a
    reading. Named `telling_back_not_checked`, a facilitator would go looking for a finding
    that was never raised, and would find the room had never been asked.
    """
    session = await ready_session(db_session)
    state = await _told_back_with_an_open_finding(db_session, session)
    state.analysed_segment_ids = None
    await reported_playback(db_session, session, state)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert blocked.value.blockers == ["telling_back_never_analysed"]


@pytest.mark.asyncio
async def test_a_session_that_never_told_anything_back_is_still_refused(
    db_session: AsyncSession,
) -> None:
    """The door that has to stay shut: nothing was told back at all."""
    session = await ready_session(db_session)
    await save_back_translation(db_session, session, BackTranslationState(scope=P))
    await retire_every_segment(db_session, session.id)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert "no_telling_back" in blocked.value.blockers


@pytest.mark.asyncio
async def test_a_checked_session_releases_exactly_as_before(db_session: AsyncSession) -> None:
    session = await ready_session(db_session)

    artifact = await build_internalization_release(db_session, session)

    assert artifact["readiness"] == "ready_for_refine"
    assert artifact["back_translation"]["checked"] is True
    assert artifact["back_translation"]["findings"] == []


@pytest.mark.asyncio
async def test_the_finding_travels_in_the_packet_the_facilitator_forced(
    db_session: AsyncSession,
) -> None:
    """A forced packet that does not name the finding is worse than the refusal it replaced.

    The release exists because a person overruled the room, so what they overruled has to be
    inside it and on the row beside it. Without that the question reaches Refine unseen, and
    unlike a blocked release that looks resolved.
    """
    session = await ready_session(db_session, project_id="time-que-discordou")
    await reported_playback(
        db_session, session, await _told_back_with_an_open_finding(db_session, session)
    )

    release = await approve_release(db_session, session, forced_by="a-facilitadora")

    carried = release.packet["back_translation"]["findings"]
    assert [finding["kind"] for finding in carried] == ["addition"]
    assert carried[0]["note"] == "a equipe disse que Noemi voltou alegre"
    assert carried[0]["segment_id"] is not None
    assert carried[0]["chunk"] == 1
    assert release.forced_open_findings == carried


@pytest.mark.asyncio
async def test_the_other_doors_are_still_shut(db_session: AsyncSession) -> None:
    """One item leaves the list; its neighbours are not loosened with it."""
    session = await ready_session(db_session)
    await reported_playback(
        db_session, session, await _told_back_with_an_open_finding(db_session, session)
    )
    await save_comprehension(db_session, session, ComprehensionState())
    session.coverage_state = {}
    await db_session.commit()

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert set(blocked.value.blockers) >= {
        "comprehension_needs_more_work",
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
    session = await ready_session(db_session)
    await save_back_translation(
        db_session,
        session,
        BackTranslationState(scope=P),
    )
    await one_stretch(db_session, session)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert "telling_back_never_analysed" in blocked.value.blockers


@pytest.mark.asyncio
async def test_what_the_team_said_before_dividing_a_stretch_still_travels(
    db_session: AsyncSession,
) -> None:
    """A divided stretch is current and is not a leaf, so it was in neither list the artifact
    carried — not the final units, not the retired ones — and what the team said about the
    whole stretch left the handoff in silence.

    The same class of loss the replaced stretches are carried against. Dividing is the team
    hearing their own recording again and finding two ideas in it, which is them working, so
    the first telling is kept rather than the division being refused.
    """
    session = await ready_session(db_session)
    whole = (await final_segments(db_session, session.id))[0]
    for half in await divide_segment(db_session, session, whole, at_ms=30000):
        await capture_segment(
            db_session,
            session,
            take_id=half.take_id,
            starts_ms=half.starts_ms,
            ends_ms=half.ends_ms,
            bridge_take_id="retro-dividido",
            transcript="o que a equipe contou sobre esta metade",
            replaces=half,
        )

    artifact = await build_internalization_release(db_session, session)

    carried = artifact["back_translation"]["divided_segments"]
    assert [one["segment_id"] for one in carried] == [whole.id]
    assert carried[0]["text"] == "Noemi voltou com Rute"
    assert whole.id not in [
        one["segment_id"] for one in artifact["back_translation"]["segments"]
    ], "e ele continua fora das unidades finais, que é o que dividir quer dizer"
    assert whole.id not in [
        one["segment_id"] for one in artifact["back_translation"]["superseded_segments"]
    ], "nem entre os aposentados, porque nada tomou o lugar dele"


async def _a_row_written_before_the_taxonomy_shrank(db: AsyncSession, session: IRSession) -> None:
    """A stored telling-back carrying a retired kind in `findings` and in a superseded one.

    Written through the room's own write path first, so the report of what the tablet played
    is bound to the rehearsal exactly as it is in the field, and only the kinds are then set
    to the names the older server wrote.
    """
    state = await _told_back_with_an_open_finding(db, session)
    state.superseded = [
        SupersededAttempt(findings=[Finding(kind=FindingKind.ADDITION, note="trocaram quem pediu")])
    ]
    await reported_playback(db, session, state)
    stored = dict(session.back_translation)
    stored["findings"] = [dict(stored["findings"][0], kind="meaning_change")]
    stored["superseded"] = [
        dict(
            stored["superseded"][0],
            findings=[dict(stored["superseded"][0]["findings"][0], kind="wrong_relation")],
        )
    ]
    session.back_translation = stored
    await db.commit()


@pytest.mark.asyncio
async def test_the_packet_carries_only_the_kinds_the_analyst_reports(
    db_session: AsyncSession,
) -> None:
    """Refine reads the three kinds, whatever the row was written with.

    A retired name reaching the packet would put a kind nobody downstream defines in front
    of the people who have to act on it, on a session the team started before the change.
    """
    session = await ready_session(db_session)
    await _a_row_written_before_the_taxonomy_shrank(db_session, session)

    artifact = await build_internalization_release(db_session, session, waived=FORCEABLE_BLOCKERS)

    assert [f["kind"] for f in artifact["back_translation"]["findings"]] == ["addition"]
    assert [
        f["kind"]
        for attempt in artifact["back_translation"]["superseded_attempts"]
        for f in attempt["findings"]
    ] == ["addition"]


@pytest.mark.asyncio
async def test_the_package_says_nothing_about_a_flag_the_room_no_longer_writes(
    db_session: AsyncSession,
) -> None:
    """A row written before the evidence flag went still ships, one finding lighter.

    Nothing migrates the row: the stored key is ignored on the way in, and the thin-evidence
    finding beside it is no finding at all. What the package carries is what the team still
    has to answer, and `checked` alone says whether the reading came out clean.
    """
    session = await ready_session(db_session)
    told = await final_segments(db_session, session.id)
    stored = dict(session.back_translation)
    stored["evidence_sufficient"] = False
    stored["checked"] = False
    stored["findings"] = [
        {"kind": "insufficient_evidence", "note": "contaram pouco", "segment_id": None},
        {"kind": "missing", "note": "Orfa não apareceu", "segment_id": told[0].id},
    ]
    stored["superseded"] = [
        {
            "findings": [
                {"kind": "insufficient_evidence", "note": "pouco na primeira", "segment_id": None}
            ],
            "evidence_sufficient": False,
            "played_ranges": [],
            "clip_duration_ms": None,
        }
    ]
    session.back_translation = stored
    await db_session.commit()

    artifact = await build_internalization_release(db_session, session, waived=FORCEABLE_BLOCKERS)

    package = artifact["back_translation"]
    assert "evidence_sufficient" not in package
    assert all("evidence_sufficient" not in attempt for attempt in package["superseded_attempts"])
    assert [f["kind"] for f in package["findings"]] == ["missing"]
    assert package["superseded_attempts"][0]["findings"] == []
    assert package["checked"] is False


@pytest.mark.asyncio
async def test_the_finding_the_packet_carries_is_counted_in_its_headline(
    db_session: AsyncSession,
) -> None:
    session = await ready_session(db_session)
    await reported_playback(
        db_session, session, await _told_back_with_an_open_finding(db_session, session)
    )

    artifact = await build_internalization_release(db_session, session, waived=FORCEABLE_BLOCKERS)

    assert artifact["open_questions"] == 1


@pytest.mark.asyncio
async def test_a_standing_swap_is_one_open_question_in_the_headline(
    db_session: AsyncSession,
) -> None:
    """The packet counts what the team was told is left, not how many rows hold it.

    A swap is two findings and one thing to do. Counted by rows, the packet tells Refine two
    questions are open on a passage the room told the team has one thing left — and Refine
    reads that headline to decide how much of the draft still needs a person.
    """
    session = await ready_session(db_session)
    state = await _told_back_with_an_open_finding(db_session, session)
    state.findings = [
        *state.findings,
        Finding(
            kind=FindingKind.MISSING,
            note="a notícia do pão não apareceu",
            segment_id=state.findings[0].segment_id,
            chunk=state.findings[0].chunk,
        ),
    ]
    await reported_playback(db_session, session, state)

    artifact = await build_internalization_release(db_session, session, waived=FORCEABLE_BLOCKERS)

    assert [finding["kind"] for finding in artifact["back_translation"]["findings"]] == [
        "addition",
        "missing",
    ]
    assert artifact["open_questions"] == 1


@pytest.mark.asyncio
async def test_a_superseded_telling_back_is_history_and_counts_nothing(
    db_session: AsyncSession,
) -> None:
    session = await ready_session(db_session)
    state = await checked_telling_back(db_session, session)
    state.superseded = [
        SupersededAttempt(findings=[Finding(kind=FindingKind.MISSING, note="Orfa")])
    ]
    await reported_playback(db_session, session, state)

    artifact = await build_internalization_release(db_session, session)

    assert artifact["open_questions"] == 0
    assert artifact["back_translation"]["superseded_attempts"][0]["findings"][0]["kind"] == (
        "missing"
    )


@pytest.mark.asyncio
async def test_the_carried_point_and_the_open_finding_add_in_the_headline(
    db_session: AsyncSession,
) -> None:
    session = await ready_session(db_session, carry_one=True)
    await reported_playback(
        db_session, session, await _told_back_with_an_open_finding(db_session, session)
    )

    artifact = await build_internalization_release(db_session, session, waived=FORCEABLE_BLOCKERS)

    assert artifact["open_questions"] == 2
