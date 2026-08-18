from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import sessions as service
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus

P = "P03"


async def test_a_later_settle_does_not_darken_an_earned_bead(db_session: AsyncSession) -> None:
    session = await service.create_session(db_session, pericope=P)
    keys = element_keys(P)
    earned = dict.fromkeys(keys, CoverageStatus.NOT_ENCOUNTERED.value)
    earned[keys[0]] = CoverageStatus.ENGAGED.value
    await service.apply_coverage(db_session, session.id, earned)

    stale = dict.fromkeys(keys, CoverageStatus.NOT_ENCOUNTERED.value)
    stale[keys[1]] = CoverageStatus.SURFACED.value
    await service.apply_coverage(db_session, session.id, stale)

    assert session.coverage_state[keys[0]] == CoverageStatus.ENGAGED.value
