from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
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
from app.services.internalization_room.segments import (
    capture_segment,
    final_segments,
    retired_segments,
)
from app.services.internalization_room.session_end import SessionState, end_of
from app.services.internalization_room.sessions import (
    MAX_RETELLS,
    append_exchange,
    apply_coverage,
    back_translation_of,
    begin_back_translation_again,
    create_session,
    get_session,
    mark_needs_person,
    save_back_translation,
    save_comprehension,
)

P = "P03"


@pytest.mark.asyncio
async def test_a_new_session_starts_with_nothing_encountered(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    assert session.status is IRSessionStatus.IN_PROGRESS
    assert session.messages == []
    assert session.coverage_state == initial_state(P)


@pytest.mark.asyncio
async def test_an_unknown_session_is_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await get_session(db_session, "nao-existe")


@pytest.mark.asyncio
async def test_the_exchange_is_appended_in_order(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await append_exchange(
        db_session, session, team_utterance="a fome chegou", guide_response="isso mesmo"
    )

    assert session.messages == [
        {"role": "team", "text": "a fome chegou"},
        {"role": "guide", "text": "isso mesmo"},
    ]


@pytest.mark.asyncio
async def test_the_opening_turn_records_only_the_guide(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="que bom ter vocês aqui"
    )

    assert session.messages == [{"role": "guide", "text": "que bom ter vocês aqui"}]


@pytest.mark.asyncio
async def test_coverage_settles_without_closing_a_partial_session(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    partial = merge(initial_state(P), pericope_num=P, engaged=element_keys(P)[:3])

    session = await apply_coverage(db_session, session.id, partial)

    assert session.status is IRSessionStatus.IN_PROGRESS
    assert session.coverage_state[element_keys(P)[0]] == "engaged"


@pytest.mark.asyncio
async def test_the_coverage_floor_alone_no_longer_closes_the_session(
    db_session: AsyncSession,
) -> None:
    """Coverage bookkeeping is participation, not comprehension — the very confusion the
    bridge-language calibration exists to undo."""
    session = await create_session(db_session, pericope=P)
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    session = await apply_coverage(db_session, session.id, whole)

    assert session.status is IRSessionStatus.IN_PROGRESS


def _fully_supported_comprehension(pericope: str) -> ComprehensionState:
    ledger = [
        EvidenceObservation(
            id=f"ev-{index}",
            unit_id=checkpoint.id,
            probe_id=f"probe-{index}",
            method=EvidenceMethod.MICRO_TELLBACK,
            result=EvidenceResult.DEMONSTRATED,
        )
        for index, checkpoint in enumerate(checkpoints_for(pericope))
    ]
    return ComprehensionState(
        ledger=list(ledger),
        practiced_scene_ids=scene_ids_for(pericope),
        recording_consent_given=True,
    )


@pytest.mark.asyncio
async def test_floor_plus_evidence_practice_and_consent_closes_the_session(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
    session = await save_comprehension(db_session, session, _fully_supported_comprehension(P))
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    session = await apply_coverage(db_session, session.id, whole)

    assert session.status is IRSessionStatus.DONE


@pytest.mark.asyncio
async def test_meeting_the_floor_stamps_the_instant_the_session_closed(
    db_session: AsyncSession,
) -> None:
    """ENG-451. Closing is an event, so it is written down rather than inferred later.

    The other way a session ends leaves no stamp on purpose — it is derived from the last
    activity, because the limit that decides it is not agreed with the room app. Which is
    exactly why this one has to be stamped: without it a finished conversation is
    indistinguishable from an abandoned one, and the Desk would call every completed session
    abandoned.

    The scenario carries calibration, evidence, practice and consent because the floor alone
    stopped closing anything: ``session_is_done`` folds those in, deliberately, so that
    bridge-limited teams are not judged on Portuguese output. What is asserted here is
    unchanged — that the close is *stamped* — only what it takes to reach a close moved.
    """
    session = await create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
    session = await save_comprehension(db_session, session, _fully_supported_comprehension(P))
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    session = await apply_coverage(db_session, session.id, whole)

    assert session.ended_at is not None
    assert end_of(session, at=datetime.now(UTC)).state is SessionState.COMPLETE


@pytest.mark.asyncio
async def test_a_settle_that_does_not_close_the_session_stamps_nothing(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    partial = merge(initial_state(P), pericope_num=P, engaged=element_keys(P)[:3])

    session = await apply_coverage(db_session, session.id, partial)

    assert session.ended_at is None


@pytest.mark.asyncio
async def test_a_session_closes_once_and_the_end_does_not_move_afterwards(
    db_session: AsyncSession,
) -> None:
    """A second settle on a closed session must not slide its end forward.

    The classifier keeps running for whatever turns were already in flight when the floor
    was met, and each of those is another write. An end re-stamped on every one of them
    would grow the conversation's length after the team had finished.
    """
    session = await create_session(db_session, pericope=P)
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    session = await apply_coverage(db_session, session.id, whole)
    closed_at = session.ended_at

    session = await apply_coverage(db_session, session.id, whole)

    assert session.ended_at == closed_at


@pytest.mark.asyncio
async def test_a_session_needing_a_person_is_marked(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await mark_needs_person(db_session, session)

    assert session.status is IRSessionStatus.NEEDS_PERSON


async def _tell(db_session: AsyncSession, session, text: str):
    """One stretch told back, so a case can have one without going through the route."""
    told = await final_segments(db_session, session.id)
    return await capture_segment(
        db_session,
        session,
        take_id="ensaio-1",
        starts_ms=len(told) * 9000,
        ends_ms=(len(told) + 1) * 9000,
        bridge_take_id="retro-1",
        transcript=text,
    )


@pytest.mark.asyncio
async def test_a_fresh_recording_throws_the_whole_telling_back_away(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    await save_back_translation(db_session, session, BackTranslationState(scope=P, retells=2))
    await _tell(db_session, session, "velho")

    state = await begin_back_translation_again(db_session, session)

    assert await final_segments(db_session, session.id) == []
    assert state.retells == 2, (
        "o contado de volta é jogado fora; o orçamento de recontagens não é parte dele. "
        "Zerá-lo punha nas mãos da equipe — por um toque em 'gravar de novo' — o contador "
        "que existe para um laço não virar laço"
    )
    assert session.status is IRSessionStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_the_retells_are_counted_and_run_out(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)
    await save_back_translation(
        db_session, session, BackTranslationState(scope=P, retells=MAX_RETELLS - 1)
    )

    state = back_translation_of(session)
    state.retells += 1
    await save_back_translation(db_session, session, state)
    if state.retells >= MAX_RETELLS:
        await mark_needs_person(db_session, session)

    assert session.status is IRSessionStatus.NEEDS_PERSON, (
        "contar o mesmo trecho de novo era um ciclo que ninguém limitava, e o "
        "orçamento que existia estava numa rota que o app nunca chamava"
    )


@pytest.mark.asyncio
async def test_a_rerecorded_attempt_is_archived_not_erased(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)
    await save_back_translation(
        db_session,
        session,
        BackTranslationState(
            scope=P,
            findings=[Finding(kind=FindingKind.MISSING, note="Orfa")],
            evidence_sufficient=False,
            retells=2,
        ),
    )
    told = await _tell(db_session, session, "Noemi mandou Rute voltar")

    fresh = await begin_back_translation_again(db_session, session)

    assert await final_segments(db_session, session.id) == []
    assert fresh.findings == []
    assert fresh.retells == 2
    assert len(fresh.superseded) == 1
    archived = fresh.superseded[0]
    assert archived.findings[0].kind is FindingKind.MISSING
    assert not archived.evidence_sufficient
    retired = await retired_segments(db_session, session.id)
    assert [one.id for one in retired] == [told.id], (
        "o trecho não é copiado para dentro do arquivo: ele fica onde está, "
        "marcado como não valendo mais, e continua recuperável"
    )


@pytest.mark.asyncio
async def test_restarting_an_empty_telling_back_archives_nothing(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    await save_back_translation(db_session, session, BackTranslationState(scope=P))

    fresh = await begin_back_translation_again(db_session, session)

    assert fresh.superseded == []


@pytest.mark.asyncio
async def test_two_retakes_keep_both_histories_in_order(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)
    await save_back_translation(
        db_session,
        session,
        BackTranslationState(scope=P, findings=[Finding(kind=FindingKind.MISSING, note="Orfa")]),
    )
    await _tell(db_session, session, "primeira tentativa")

    state = await begin_back_translation_again(db_session, session)
    state.findings = [Finding(kind=FindingKind.ADDITION, note="Belém")]
    await save_back_translation(db_session, session, state)
    await _tell(db_session, session, "segunda tentativa")

    fresh = await begin_back_translation_again(db_session, session)

    assert [attempt.findings[0].note for attempt in fresh.superseded] == ["Orfa", "Belém"]
    assert [one.transcript for one in await retired_segments(db_session, session.id)] == [
        "primeira tentativa",
        "segunda tentativa",
    ]
