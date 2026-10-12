"""ENG-1412 — two coverage settles landing together keep every bead either of them lit.

`apply_coverage` merged what the classifier told against the coverage it had just read, and
wrote the merge over whatever was stored by the time it wrote. A second settle landing in
between had its bead written over by a merge that never saw it, and the tablet's bead went
dark again.

The rival settle lands right after this one read the session, on a session of its own, the way
a second Cloud Run instance would land it: after this settle read the coverage and before it
wrote.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRCoverageEvent, IRSession
from app.services.internalization_room import sessions as service
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus

P = "P03"
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
