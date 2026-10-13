from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room import sessions as service
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus

P = "P03"
LIT = CoverageStatus.ENGAGED.value


def _the_whole_floor() -> dict[str, str]:
    return dict.fromkeys(element_keys(P), LIT)


def _a_rival_lands_after_the_read(
    monkeypatch,
    rival_factory: async_sessionmaker[AsyncSession],
    rival: Callable[[AsyncSession, IRSession], Awaitable[object]],
) -> None:
    read = service.get_session
    landed = False

    async def racing(db: AsyncSession, session_id: str) -> IRSession:
        nonlocal landed
        session = await read(db, session_id)
        if not landed:
            landed = True
            async with rival_factory() as rival_db:
                await rival(rival_db, await read(rival_db, session_id))
        return session

    monkeypatch.setattr(service, "get_session", racing)


async def _stored(rival_factory: async_sessionmaker[AsyncSession], session_id: str) -> IRSession:
    async with rival_factory() as fresh_db:
        return await service.get_session(fresh_db, session_id)


async def test_a_halt_raised_while_the_floor_was_settling_stands_and_its_lift_reads_done(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    session = await service.create_session(db_session, pericope=P)
    _a_rival_lands_after_the_read(monkeypatch, rival_factory, service.mark_needs_person)

    before = datetime.now(UTC)
    await service.apply_coverage(db_session, session.id, _the_whole_floor())
    after = datetime.now(UTC)

    halted = await _stored(rival_factory, session.id)
    assert halted.status is IRSessionStatus.NEEDS_PERSON, (
        "o fechamento gravava done por cima do pedido de pessoa, e o tablet esperava alguém "
        "numa passagem que a linha dizia encerrada"
    )
    assert halted.ended_at is not None and before <= halted.ended_at <= after, (
        "o fechamento recusado largava o carimbo do piso junto com o status, e nada mais "
        "dizia que a passagem tinha sido terminada"
    )
    async with rival_factory() as visit_db:
        visited = await service.get_session(visit_db, session.id)
        lifted = await service.attend(visit_db, visited, by="facilitator")
    assert (lifted.status, lifted.ended_at) == (IRSessionStatus.DONE, halted.ended_at), (
        "a visita levantava o pedido para em andamento, e a passagem terminada nunca entrava "
        "nas concluídas"
    )


async def test_two_settles_meeting_the_floor_together_keep_the_first_end_not_a_second(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    session = await service.create_session(db_session, pericope=P)
    closed: list[IRSession] = []

    async def a_rival_closes(rival_db: AsyncSession, rivals: IRSession) -> None:
        closed.append(await service.apply_coverage(rival_db, rivals.id, _the_whole_floor()))

    _a_rival_lands_after_the_read(monkeypatch, rival_factory, a_rival_closes)

    await service.apply_coverage(db_session, session.id, _the_whole_floor())

    stored = await _stored(rival_factory, session.id)
    (first,) = closed
    assert first.ended_at is not None
    assert (stored.status, stored.ended_at) == (IRSessionStatus.DONE, first.ended_at), (
        "o segundo settle carimbava outro fim por cima do primeiro, e a conversa crescia "
        "depois que a equipe tinha terminado"
    )


async def test_a_visit_undone_while_the_floor_was_settling_brings_the_halt_back_not_done(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession], monkeypatch
) -> None:
    session = await service.create_session(db_session, pericope=P)
    session = await service.mark_needs_person(db_session, session)
    session = await service.attend(db_session, session, by="facilitator")
    assert session.status is IRSessionStatus.IN_PROGRESS
    _a_rival_lands_after_the_read(monkeypatch, rival_factory, service.unattend)

    await service.apply_coverage(db_session, session.id, _the_whole_floor())

    stored = await _stored(rival_factory, session.id)
    assert stored.status is IRSessionStatus.NEEDS_PERSON, (
        "a visita desfeita devolvia o pedido de pessoa, e o fechamento gravava done por cima dele"
    )
    assert stored.ended_at is not None, "o fechamento recusado largava o carimbo do piso"


async def test_a_room_already_halted_when_the_floor_is_met_keeps_the_halt_and_the_stamp(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await service.create_session(db_session, pericope=P)
    await service.mark_needs_person(db_session, session)

    before = datetime.now(UTC)
    await service.apply_coverage(db_session, session.id, _the_whole_floor())
    after = datetime.now(UTC)

    halted = await _stored(rival_factory, session.id)
    assert halted.status is IRSessionStatus.NEEDS_PERSON
    assert halted.ended_at is not None and before <= halted.ended_at <= after, (
        "o piso cumprido numa sala parada não deixava carimbo, e a visita a devolvia em andamento"
    )
