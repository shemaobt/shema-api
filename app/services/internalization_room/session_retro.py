from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.models.internalization_room import (
    SessionRetroCheck,
    SessionRetroCheckFinding,
    SessionRetroResponse,
)
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.check_block import check_status, standing_state
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.takes import takes_of


async def retro_of(db: AsyncSession, session: IRSession) -> SessionRetroResponse:
    takes = await takes_of(db, session.id)
    telling_back = await standing_state(db, session.id, back_translation_of(session), takes)
    approved = await approved_draft(db, session)
    return SessionRetroResponse(
        session_id=session.id,
        status=check_status(telling_back.checked, False),
        version=approved.version if approved else None,
        approved_at=approved.approved_at.isoformat() if approved else None,
        checks=[
            SessionRetroCheck(
                at=check.at.isoformat(),
                outcome=check.outcome,
                conferida=check.conferida,
                spoken=check.spoken,
                findings=[
                    SessionRetroCheckFinding(kind=finding.kind.value, frase=finding.chunk)
                    for finding in check.findings
                ],
            )
            for check in telling_back.checks
        ],
    )
