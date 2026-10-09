from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from scripts import hold_deploy

NOW = datetime(2026, 10, 8, 14, 0, tzinfo=UTC)
HOUR = timedelta(minutes=60)


async def a_session(db: AsyncSession, session_id: str, **columns: Any) -> None:
    db.add(
        IRSession(
            **{
                "id": session_id,
                "pericope": "P03",
                "project_id": "time-de-ruth",
                "messages": [{"role": "user", "content": "Noemi voltou para Belém."}],
                "updated_at": NOW - timedelta(minutes=5),
                **columns,
            }
        )
    )
    await db.commit()


async def test_a_team_in_the_middle_of_a_passage_holds_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(db_session, "sessao-da-ruth")

    held = await hold_deploy.holding(db_session, NOW, HOUR)

    assert [session.id for session in held] == ["sessao-da-ruth"]


async def test_a_session_opened_with_no_team_never_holds_the_deploy(
    db_session: AsyncSession,
) -> None:
    await a_session(db_session, "sessao-da-chave-da-sala", project_id=None)

    assert await hold_deploy.holding(db_session, NOW, HOUR) == []
