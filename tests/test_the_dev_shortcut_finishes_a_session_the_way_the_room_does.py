"""ENG-1263 — `scripts/dev_avancar_sessao.py` takes a session to the floor as the room does.

A session the shortcut calls done must read as done everywhere: the Desk's card says
complete, and a halt on its closed passage is refused.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PassageClosed
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room.session_end import SessionState, end_of
from app.services.internalization_room.sessions import create_session, mark_needs_person
from scripts.dev_avancar_sessao import advance
from tests.release_harness import P


async def test_a_session_the_shortcut_finished_reads_complete_at_the_desk(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)

    await advance(db_session, session)

    assert session.status is IRSessionStatus.DONE
    assert end_of(session).state is SessionState.COMPLETE


async def test_a_halt_on_a_session_the_shortcut_finished_is_refused(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    await advance(db_session, session)

    with pytest.raises(PassageClosed):
        await mark_needs_person(db_session, session)
