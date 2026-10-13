"""ENG-1412 — two writes of the check's state landing together keep what each of them added.

`save_back_translation` wrote the whole telling-back state the caller held, and the caller
held what it read before an analyst round trip. A second write landing in between — another
`terminei`, a capture, a playback report — was written over by a state that never saw it, and
its findings and its kept check round were gone with neither writer told.

Each writer reads the session on a session of its own, the way two requests would, and both
read before either writes.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import sessions as service
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CheckRound,
    Finding,
    FindingKind,
    Nuance,
)

P = "P03"
SESSIONS_LOGGER = "app.services.internalization_room.sessions"


def _finding(note: str) -> Finding:
    return Finding(kind=FindingKind.MISSING, note=note, chunk=1)


def _nuance(story: str) -> Nuance:
    return Nuance(
        note=story,
        chunk=1,
        segment_id=f"trecho de {story}",
        quote="Rute",
        story=story,
        take_id="parte-1",
        starts_ms=0,
        ends_ms=4200,
    )


def _round(spoken: str, *findings: Finding) -> CheckRound:
    return CheckRound(
        at=datetime.now(UTC),
        findings=list(findings),
        spoken=spoken,
        outcome="pass",
        conferida=False,
    )


async def _read(db: AsyncSession, session_id: str) -> tuple[IRSession, BackTranslationState]:
    session = await service.get_session(db, session_id)
    return session, service.back_translation_of(session)


async def _stored(
    rival_factory: async_sessionmaker[AsyncSession], session_id: str
) -> BackTranslationState:
    async with rival_factory() as fresh_db:
        return service.back_translation_of(await service.get_session(fresh_db, session_id))


async def test_two_check_writes_at_once_each_adding_a_finding_keep_both_findings_and_rounds(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession], caplog
) -> None:
    session = await service.create_session(db_session, pericope=P)
    async with rival_factory() as first_db, rival_factory() as second_db:
        first, first_state = await _read(first_db, session.id)
        second, second_state = await _read(second_db, session.id)

        second_state.findings.append(_finding("faltou o nome de Boaz"))
        second_state.checks.append(_round("segunda rodada", _finding("faltou o nome de Boaz")))
        await service.save_back_translation(second_db, second, second_state)
        first_state.findings.append(_finding("faltou a colheita"))
        first_state.checks.append(_round("primeira rodada", _finding("faltou a colheita")))
        with caplog.at_level(logging.WARNING, logger=SESSIONS_LOGGER):
            await service.save_back_translation(first_db, first, first_state)

    stored = await _stored(rival_factory, session.id)
    assert sorted(finding.note for finding in stored.findings) == [
        "faltou a colheita",
        "faltou o nome de Boaz",
    ], "a escrita que leu antes gravava o estado inteiro por cima, e o achado da outra sumia"
    assert sorted(check.spoken for check in stored.checks) == [
        "primeira rodada",
        "segunda rodada",
    ], "a rodada guardada pela outra escrita sumia junto com o achado"
    assert any(
        "stale read" in record.getMessage() and "back_translation" in record.getMessage()
        for record in caplog.records
    )


async def test_a_finding_one_write_took_away_stays_away_when_a_write_that_read_it_lands_first(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await service.create_session(db_session, pericope=P)
    state = service.back_translation_of(session)
    state.findings.append(_finding("sobre a parte gravada de novo"))
    await service.save_back_translation(db_session, session, state)
    async with rival_factory() as checking_db, rival_factory() as retiring_db:
        checking, checking_state = await _read(checking_db, session.id)
        retiring, retiring_state = await _read(retiring_db, session.id)

        checking_state.findings.append(_finding("faltou a colheita"))
        await service.save_back_translation(checking_db, checking, checking_state)
        retiring_state.findings = []
        await service.save_back_translation(retiring_db, retiring, retiring_state)

    stored = await _stored(rival_factory, session.id)
    assert [finding.note for finding in stored.findings] == ["faltou a colheita"], (
        "o achado sobre o áudio aposentado voltava pela escrita que o tinha lido antes"
    )


async def test_a_playback_report_read_before_a_check_lands_its_listening_and_keeps_the_check(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await service.create_session(db_session, pericope=P)
    async with rival_factory() as checking_db, rival_factory() as reporting_db:
        checking, checking_state = await _read(checking_db, session.id)
        reporting, reporting_state = await _read(reporting_db, session.id)

        checking_state.checked = True
        await service.save_back_translation(checking_db, checking, checking_state)
        reporting_state.played_ranges = [[0, 4200]]
        reporting_state.clip_duration_ms = 4200
        await service.save_back_translation(reporting_db, reporting, reporting_state)

    stored = await _stored(rival_factory, session.id)
    assert (stored.checked, stored.played_ranges, stored.clip_duration_ms) == (
        True,
        [[0, 4200]],
        4200,
    ), "o relatório de escuta refeito sobre a leitura nova perdia o que ele mesmo trazia"


async def test_a_caller_saving_again_after_its_write_was_redone_keeps_the_other_writes_finding(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await service.create_session(db_session, pericope=P)
    async with rival_factory() as checking_db, rival_factory() as finishing_db:
        checking, checking_state = await _read(checking_db, session.id)
        finishing, finishing_state = await _read(finishing_db, session.id)

        checking_state.findings.append(_finding("faltou o nome de Boaz"))
        await service.save_back_translation(checking_db, checking, checking_state)
        finishing_state.played_ranges = [[0, 4200]]
        await service.save_back_translation(finishing_db, finishing, finishing_state)
        finishing_state.waited += 1
        await service.save_back_translation(finishing_db, finishing, finishing_state)

    stored = await _stored(rival_factory, session.id)
    assert [finding.note for finding in stored.findings] == ["faltou o nome de Boaz"], (
        "a segunda gravação do mesmo estado lia o achado da outra escrita como retirado"
    )
    assert (stored.played_ranges, stored.waited) == ([[0, 4200]], 1)


async def test_a_state_stored_as_json_null_matches_its_own_reading_and_the_save_lands(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await service.create_session(db_session, pericope=P)
    await db_session.execute(
        text("UPDATE ir_sessions SET back_translation = 'null' WHERE id = :id"), {"id": session.id}
    )
    await db_session.commit()
    async with rival_factory() as first_db:
        first, state = await _read(first_db, session.id)

        state.findings.append(_finding("faltou a colheita"))
        await service.save_back_translation(first_db, first, state)

    stored = await _stored(rival_factory, session.id)
    assert [finding.note for finding in stored.findings] == ["faltou a colheita"], (
        "o null guardado não casava com a própria leitura, e a gravação era recusada até desistir"
    )


async def test_a_finding_identical_to_one_already_kept_is_a_second_finding_not_the_same_one(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await service.create_session(db_session, pericope=P)
    state = service.back_translation_of(session)
    state.findings.append(_finding("faltou a colheita"))
    await service.save_back_translation(db_session, session, state)
    async with rival_factory() as checking_db, rival_factory() as capturing_db:
        checking, checking_state = await _read(checking_db, session.id)
        capturing, capturing_state = await _read(capturing_db, session.id)

        capturing_state.checked = True
        await service.save_back_translation(capturing_db, capturing, capturing_state)
        checking_state.findings.append(_finding("faltou a colheita"))
        await service.save_back_translation(checking_db, checking, checking_state)

    stored = await _stored(rival_factory, session.id)
    assert [finding.note for finding in stored.findings] == [
        "faltou a colheita",
        "faltou a colheita",
    ], "dois achados idênticos viravam um só na mescla, e o segundo sumia da lista"


async def test_a_check_redone_over_a_write_that_left_the_findings_alone_keeps_its_own_order(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await service.create_session(db_session, pericope=P)
    state = service.back_translation_of(session)
    state.findings.append(_finding("faltou a colheita"))
    await service.save_back_translation(db_session, session, state)
    async with rival_factory() as checking_db, rival_factory() as reading_db:
        checking, checking_state = await _read(checking_db, session.id)
        reading, reading_state = await _read(reading_db, session.id)

        reading_state.waited = 1
        await service.save_back_translation(reading_db, reading, reading_state)
        checking_state.findings = [_finding("faltou o nome de Boaz"), _finding("faltou a colheita")]
        await service.save_back_translation(checking_db, checking, checking_state)

    stored = await _stored(rival_factory, session.id)
    assert [finding.note for finding in stored.findings] == [
        "faltou o nome de Boaz",
        "faltou a colheita",
    ], "a mescla punha o achado novo atrás dos antigos, e a sala lia como líder outro achado"


async def test_a_nuance_one_write_took_away_stays_away_and_the_other_writes_nuance_stays(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await service.create_session(db_session, pericope=P)
    state = service.back_translation_of(session)
    state.nuances = [_nuance("sobre a parte gravada de novo")]
    await service.save_back_translation(db_session, session, state)
    async with rival_factory() as checking_db, rival_factory() as retiring_db:
        checking, checking_state = await _read(checking_db, session.id)
        retiring, retiring_state = await _read(retiring_db, session.id)

        checking_state.nuances = [*checking_state.nuances, _nuance("Rute fica com Noemi")]
        await service.save_back_translation(checking_db, checking, checking_state)
        retiring_state.nuances = []
        await service.save_back_translation(retiring_db, retiring, retiring_state)

    stored = await _stored(rival_factory, session.id)
    assert [nuance.story for nuance in stored.nuances] == ["Rute fica com Noemi"], (
        "a escrita refeita gravava a lista de detalhes inteira, e o detalhe novo da outra sumia"
    )
