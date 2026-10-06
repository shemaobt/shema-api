"""A session with no team opens on an empty necklace.

Since ENG-1237 every session the room creates starts with each bead at not encountered, as
hers does (`freshState`, `src/session/store.ts`): nothing is carried over from a team's
earlier sessions. Work with no project is the case that never carried anything, and it stays.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import CoverageStatus

NOT_ENCOUNTERED = CoverageStatus.NOT_ENCOUNTERED.value
ENGAGED = CoverageStatus.ENGAGED.value

FIRST = load_book(ROOM_BOOK)[0].pericope_num


async def test_a_tablet_that_never_said_whose_it_is_still_opens_on_an_empty_necklace(
    db_session: AsyncSession,
) -> None:
    """Work with no project is nobody's rather than everybody's.

    The room app sends its device credential only from ENG-454 onward, so a session with no
    team is the common case in the field rather than the exception — and there is no history
    to read for one. Carrying the unowned beads instead would hand every such tablet the
    accumulated work of every other unowned tablet in the installation.
    """
    keys = element_keys(FIRST)
    somebody_elses = await room.create_session(db_session, pericope=FIRST, project_id=None)
    await room.apply_coverage(db_session, somebody_elses.id, {keys[0]: ENGAGED})

    session = await room.create_session(db_session, pericope=FIRST, project_id=None)

    assert session.coverage_state == dict.fromkeys(keys, NOT_ENCOUNTERED)
