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

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import sessions as service
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CheckRound,
    Finding,
    FindingKind,
)

P = "P03"
SESSIONS_LOGGER = "app.services.internalization_room.sessions"


def _finding(note: str) -> Finding:
    return Finding(kind=FindingKind.MISSING, note=note, chunk=1)


def _round(spoken: str, *findings: Finding) -> CheckRound:
    return CheckRound(
        at=datetime.now(UTC),
        findings=list(findings),
        spoken=spoken,
        outcome="pass",
        conferida=False,
    )


async def _read(
    rival_factory: async_sessionmaker[AsyncSession], session_id: str
) -> tuple[AsyncSession, IRSession, BackTranslationState]:
    db = rival_factory()
    session = await service.get_session(db, session_id)
    return db, session, service.back_translation_of(session)


async def _stored(
    rival_factory: async_sessionmaker[AsyncSession], session_id: str
) -> BackTranslationState:
    async with rival_factory() as fresh_db:
        return service.back_translation_of(await service.get_session(fresh_db, session_id))


async def test_two_check_writes_at_once_each_adding_a_finding_keep_both_findings_and_rounds(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession], caplog
) -> None:
    session = await service.create_session(db_session, pericope=P)
    first_db, first, first_state = await _read(rival_factory, session.id)
    second_db, second, second_state = await _read(rival_factory, session.id)

    second_state.findings.append(_finding("faltou o nome de Boaz"))
    second_state.checks.append(_round("segunda rodada", _finding("faltou o nome de Boaz")))
    await service.save_back_translation(second_db, second, second_state)
    first_state.findings.append(_finding("faltou a colheita"))
    first_state.checks.append(_round("primeira rodada", _finding("faltou a colheita")))
    with caplog.at_level(logging.WARNING, logger=SESSIONS_LOGGER):
        await service.save_back_translation(first_db, first, first_state)
    await first_db.close()
    await second_db.close()

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
    checking_db, checking, checking_state = await _read(rival_factory, session.id)
    retiring_db, retiring, retiring_state = await _read(rival_factory, session.id)

    checking_state.findings.append(_finding("faltou a colheita"))
    await service.save_back_translation(checking_db, checking, checking_state)
    retiring_state.findings = []
    await service.save_back_translation(retiring_db, retiring, retiring_state)
    await checking_db.close()
    await retiring_db.close()

    stored = await _stored(rival_factory, session.id)
    assert [finding.note for finding in stored.findings] == ["faltou a colheita"], (
        "o achado sobre o áudio aposentado voltava pela escrita que o tinha lido antes"
    )
