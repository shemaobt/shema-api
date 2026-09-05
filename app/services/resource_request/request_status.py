from datetime import datetime
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRDecision, RRStage
from app.services.resource_request._evaluation import team_outcome
from app.services.resource_request.get_request import get_request


class RequestStatus(NamedTuple):
    stage: RRStage
    submitted_at: datetime | None
    decision: RRDecision | None
    team_note: str | None


async def request_status(
    db: AsyncSession, request_id: str, user: User, app_key: str
) -> RequestStatus:
    """What a team is told about its request — GATE-03 D4's *status and nothing else*.

    Four values and no more, and the ceiling is the point: ``stage`` and ``submitted_at``
    are the journey, ``decision`` is the outcome the team is entitled to, and ``team_note``
    is the one sentence of the evaluation aggregate addressed **to the team** (client,
    28/aug/2026) — the team does not start reading the evaluation, it starts reading a
    message. Scores, comments, attendees and the evaluator never leave this function,
    and they are never selected in the first place.

    The row scope is ``get_request``'s: a team reaches its own requests and meets the same
    404 as *does not exist* for anyone else's, while mesa and Gestor read any — they hold
    ``view_evaluation`` anyway, so this projection hides nothing from them that another
    route would not show whole.

    **It reads two columns of the evaluation and not the aggregate**, through
    ``team_outcome``: this is the route a team refreshes, and ``load_evaluation`` served it
    the six score rows, the ata and the snapshot's whole frozen document to drop all three.
    The scoped spine read stays whole — it is ``get_request``'s, and one owner of the row
    scope is worth more here than the two statements a second door would save.
    """
    request = (await get_request(db, request_id, user, app_key)).request
    decision, team_note = await team_outcome(db, request_id)

    return RequestStatus(
        stage=request.stage,
        submitted_at=request.submitted_at,
        decision=decision,
        team_note=team_note,
    )
