"""ENG-1412 — two coverage settles landing together keep every bead either of them lit.

`apply_coverage` merged what the classifier told against the coverage it had just read, and
wrote the merge over whatever was stored by the time it wrote. A second settle landing in
between had its bead written over by a merge that never saw it, and the tablet's bead went
dark again.

The rival settle lands right after this one read the session, on a session of its own, the way
a second Cloud Run instance would land it: after this settle read the coverage and before it
wrote.
"""

import asyncio
import json
import logging

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import ConflictError
from app.db.models.internalization_room import IRCoverageEvent, IRSession
from app.services.internalization_room import sessions as service
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus

P = "P03"
SESSIONS_LOGGER = "app.services.internalization_room.sessions"
LIT = CoverageStatus.ENGAGED.value
DARK = CoverageStatus.NOT_ENCOUNTERED.value


def _lighting(*keys: str) -> dict[str, str]:
    told = dict.fromkeys(element_keys(P), DARK)
    told.update(dict.fromkeys(keys, LIT))
    return told


def _a_rival_settles_after_the_read(
    monkeypatch, rival_factory: async_sessionmaker[AsyncSession], told: dict[str, str]
) -> None:
    read = service.get_session
    landed = False

    async def racing(db: AsyncSession, session_id: str) -> IRSession:
        nonlocal landed
        session = await read(db, session_id)
        if not landed:
            landed = True
            async with rival_factory() as rival_db:
                await service.apply_coverage(rival_db, session_id, told)
        return session

    monkeypatch.setattr(service, "get_session", racing)


async def _stored_coverage(
    rival_factory: async_sessionmaker[AsyncSession], session_id: str
) -> dict[str, str]:
    async with rival_factory() as fresh_db:
        return (await service.get_session(fresh_db, session_id)).coverage_state


async def test_two_settles_at_once_each_lighting_a_bead_leave_both_lit_not_only_the_last(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P)
    _a_rival_settles_after_the_read(monkeypatch, rival_factory, _lighting(keys[1]))

    await service.apply_coverage(db_session, session.id, _lighting(keys[0]))

    stored = await _stored_coverage(rival_factory, session.id)
    assert (stored[keys[0]], stored[keys[1]]) == (LIT, LIT), (
        "o segundo settle gravava a mescla que nunca viu o primeiro, e a conta acesa apagava"
    )


async def test_two_settles_at_once_lighting_the_same_bead_leave_one_event_for_it_not_two(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P)
    _a_rival_settles_after_the_read(monkeypatch, rival_factory, _lighting(keys[0]))

    await service.apply_coverage(db_session, session.id, _lighting(keys[0]))

    async with rival_factory() as fresh_db:
        events = (
            await fresh_db.scalars(
                select(IRCoverageEvent).where(
                    IRCoverageEvent.session_id == session.id,
                    IRCoverageEvent.element_key == keys[0],
                )
            )
        ).all()
    assert len(events) == 1, (
        "o segundo settle contava a transição contra a leitura velha, e a conta ganhava dois "
        "toques para um só acendimento"
    )


async def test_a_settle_refused_for_a_stale_read_says_so_in_the_log_before_it_is_redone(
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch,
    caplog,
) -> None:
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P)
    _a_rival_settles_after_the_read(monkeypatch, rival_factory, _lighting(keys[1]))

    with caplog.at_level(logging.WARNING, logger=SESSIONS_LOGGER):
        await service.apply_coverage(db_session, session.id, _lighting(keys[0]))

    stale = [r.getMessage() for r in caplog.records if "stale read" in r.getMessage()]
    assert len(stale) == 1, "a leitura velha era escrita por cima calada, sem linha nenhuma no log"
    assert session.id in stale[0] and "coverage_state" in stale[0]


async def test_a_settle_landing_while_a_turn_is_in_flight_lets_the_turn_land_not_a_conflict(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P)

    async with rival_factory() as settle_db:
        await service.apply_coverage(settle_db, session.id, _lighting(keys[0]))

    await service.append_exchange(db_session, session, team_utterance="oi", guide_response="ola")

    async with rival_factory() as fresh_db:
        landed = await service.get_session(fresh_db, session.id)
    assert [message["text"] for message in landed.messages] == ["oi", "ola"], (
        "um settle que movesse a versão da sessão devolvia 409 a todo turno em voo"
    )
    assert landed.coverage_state[keys[0]] == LIT


async def test_a_settle_whose_reading_never_matches_gives_up_after_five_tries_not_forever(
    db_session: AsyncSession, monkeypatch, caplog
) -> None:
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P)
    unmatchable = json.dumps(session.coverage_state, separators=(",", ":"))
    await db_session.execute(
        text("UPDATE ir_sessions SET coverage_state = :stored WHERE id = :id"),
        {"stored": unmatchable, "id": session.id},
    )
    await db_session.commit()
    db_session.expunge_all()

    with (
        caplog.at_level(logging.WARNING, logger=SESSIONS_LOGGER),
        pytest.raises(ConflictError),
    ):
        await asyncio.wait_for(
            service.apply_coverage(db_session, session.id, _lighting(keys[0])), timeout=5
        )

    refusals = [r for r in caplog.records if "stale read" in r.getMessage()]
    assert len(refusals) == 5, "uma comparação que nunca casa girava para sempre, presa à conexão"
