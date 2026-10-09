"""The coordination hears that a sensitive project's prayer request waits for it (OBT-575).

Karina, via Daniel, 6/oct/2026: on a sensitive project the coordination reviews the text before it
goes to the wall and the Pulse. A queue nobody hears of is a queue that waits, so a write that
leaves a request waiting which was not waiting before stages one notice for the coordination of
the project's region — the Pulse applied with ``rede``, a need shared in the ficha, a new text, a
project flagged sensitive with requests already on the wall. Which requests wait is
``_consent.awaiting_review``'s question; this file compares the answer before and after a write
and addresses the notice.

**The coordination of the region and nobody else.** ``coordinator`` holders whose scope reaches
the project's region, by ``_scope.holders_reaching`` — the regional coordination that releases.
The Resource Circle hears of the request when it reaches the wall, as OBT-566 has it, and the OBT
Lab neither reviews nor releases. **The person whose write it was is not told**, ``_needs.py``'s
rule for the urgent need: they know.

**What waits, never what it says.** The notice is a project kind with the project's id as its one
fact (OBT-559): the PME words it in its reader's language and reads the name off the project,
and the English ``title`` and ``body`` beside it carry the name as everybody outside coordination
reads it and no word of the request.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.models.shema_privacy import ShemaReader
from app.services import authorization_service
from app.services.notifications import get_shema_app_id
from app.services.notifications.get_shema_app_id import SHEMA_APP_KEY
from app.services.shema._project_notices import ProjectNoticeFacts, stage_project_notice
from app.services.shema._redaction import language_name_for
from app.services.shema._scope import (
    COORDINATOR_ROLE,
    Readership,
    RegionScope,
    holders_reaching,
)

logger = logging.getLogger(__name__)

#: Who is told that a request waits — the role that releases it.
REVIEW_ROLES = (COORDINATOR_ROLE,)

REVIEW_EVENT = "shema.prayer.review"


async def notify_review(
    db: AsyncSession,
    project: ShemaProject,
    *,
    before: frozenset[str],
    now: frozenset[str],
    actor: User | None,
) -> int:
    """Tell the region's coordination when ``now`` holds a request ``before`` did not.

    ``before`` and ``now`` are ``_consent.awaiting_ids`` read around the write. A request that
    stopped waiting, or one that was already waiting, is not news. Staged inside the caller's
    transaction, so the notice lands with the write that made the request wait, or neither does.
    Answers how many were staged.
    """
    if not now - before:
        return 0
    holders = await authorization_service.list_role_holders(db, SHEMA_APP_KEY, REVIEW_ROLES)
    reaching = await holders_reaching(db, holders, project.region_key, SHEMA_APP_KEY)
    recipients = [person for person in reaching if actor is None or person.id != actor.id]
    if not recipients:
        return 0
    app_id = await get_shema_app_id(db)
    language = language_name_for(project, ShemaReader.OTHER, fallback="") or "a project"
    for person in recipients:
        await stage_project_notice(
            db,
            user_id=person.id,
            app_id=app_id,
            event_type=REVIEW_EVENT,
            title=f"Prayer request to review — {language}",
            body=(
                f"A prayer request the team of {language} shared is waiting for the "
                "coordination's review before it reaches the wall and the Pulse."
            ),
            facts=ProjectNoticeFacts(project_id=project.id),
            actor_id=None if actor is None else actor.id,
        )
    return len(recipients)


def refuse_unless_coordination(
    readership: Readership, *, user: User, operation: str
) -> RegionScope:
    """The regions this caller releases in — or a 403 for a caller who coordinates none.

    *Liberar e editar são só da coordenação* (the issue's DoD): the regional coordinator in its
    own regions and the ``admin`` who coordinates every one (``_scope.readership``). The Resource
    Circle reads the truth and releases nothing (OBT-571), and the OBT Lab, the teams and the
    other roles coordinate no region. The answer is the scope the caller's queue and release are
    read through, so a project in a region it does not coordinate is the existence-hiding 404.
    """
    coordination = readership.coordination
    if coordination.global_ or coordination.regions:
        return coordination
    logger.warning(
        "shema authorization refused: only the coordination releases a prayer request",
        extra={"shema_operation": operation, "shema_user_id": user.id},
    )
    raise AuthorizationError(
        "Only the coordination reviews and releases a sensitive project's prayer request"
    )
