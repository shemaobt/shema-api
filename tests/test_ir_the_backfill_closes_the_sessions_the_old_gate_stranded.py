from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRCoverageEvent, IRSession, IRSessionStatus
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.sessions import create_session
from scripts.backfill_floor_done_sessions import backfill
from tests.baker import make_language, make_project
from tests.release_harness import ensaio_take

P = "P01"
EARLIER = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
REACHED = datetime(2026, 9, 20, 14, 30, tzinfo=UTC)
AFTERWARDS = datetime(2026, 9, 20, 14, 45, tzinfo=UTC)
LAST_TOUCHED = datetime(2026, 9, 21, 9, 15, tzinfo=UTC)


async def _stranded(db: AsyncSession, *, project_id: str | None = None) -> IRSession:
    session = await create_session(db, language="pt", pericope=P, project_id=project_id)
    keys = element_keys(P)
    session.coverage_state = dict.fromkeys(keys, "engaged")
    for key, at in [
        (keys[0], AFTERWARDS),
        *((key, EARLIER) for key in keys[:-1]),
        (keys[-1], REACHED),
    ]:
        db.add(
            IRCoverageEvent(
                session_id=session.id,
                project_id=project_id,
                pericope=P,
                element_key=key,
                status="engaged",
                at=at,
            )
        )
    await db.commit()
    return session


async def test_a_dry_run_names_the_instant_and_writes_nothing(db_session: AsyncSession) -> None:
    session = await _stranded(db_session)

    report = await backfill(db_session, apply=False)
    await db_session.refresh(session)

    assert session.status is IRSessionStatus.IN_PROGRESS
    assert session.ended_at is None
    assert any(session.id in line and REACHED.isoformat() in line for line in report), report


async def test_the_session_closes_at_the_instant_its_events_met_the_floor(
    db_session: AsyncSession,
) -> None:
    session = await _stranded(db_session)

    await backfill(db_session, apply=True)
    await db_session.refresh(session)

    assert session.status is IRSessionStatus.DONE
    assert session.ended_at == REACHED, "a sessão presa fechava no instante da migração"


async def test_a_session_whose_events_never_met_the_floor_closes_at_its_last_update(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    session.coverage_state = dict.fromkeys(element_keys(P), "engaged")
    await db_session.commit()
    await db_session.execute(
        update(IRSession).where(IRSession.id == session.id).values(updated_at=LAST_TOUCHED)
    )
    await db_session.commit()

    report = await backfill(db_session, apply=True)
    await db_session.refresh(session)

    assert session.ended_at == LAST_TOUCHED
    assert session.updated_at == LAST_TOUCHED, (
        "o backfill punha as sessões fechadas no topo da fila da facilitadora"
    )
    assert any(
        session.id in line and LAST_TOUCHED.isoformat() in line and "updated_at" in line
        for line in report
    ), report


async def test_a_room_waiting_on_a_person_at_the_floor_is_listed_and_left_as_it_is(
    db_session: AsyncSession,
) -> None:
    session = await _stranded(db_session)
    session.status = IRSessionStatus.NEEDS_PERSON
    await db_session.commit()

    report = await backfill(db_session, apply=True)
    await db_session.refresh(session)

    assert session.status is IRSessionStatus.NEEDS_PERSON
    assert session.ended_at is None
    assert any(session.id in line and "needs_person" in line for line in report), report


async def test_each_team_hears_which_passage_finishes_and_where_it_goes_next(
    db_session: AsyncSession,
) -> None:
    language = await make_language(db_session)
    project = await make_project(db_session, language.id)
    session = await _stranded(db_session, project_id=project.id)
    team = project.id
    db_session.add(ensaio_take(session.id, project_id=team))
    await db_session.commit()

    report = await backfill(db_session, apply=False)

    assert f"team {team}: finishes P01; active passage P01 -> P02" in report, report
