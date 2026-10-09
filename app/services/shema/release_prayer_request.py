"""The coordination releases a sensitive project's prayer request — and may edit it first (OBT-575).

Karina, via Daniel, 6/oct/2026: *"A coordenação revisa o texto antes de ele ir ao mural e ao
Pulso."* The release is ``_consent.release_request``'s, the one writer of the columns it moves;
this file finds the request inside the caller's coordination and commits.

**The Resource Circle hears of the request here**, when it reaches the wall (OBT-566's rule, moved
for a sensitive project from the Pulse's apply to this release): the apply put nothing on the wall
for it to hear of. Only for what the apply would have announced — the project's own request, a
Pulse brought and shared (``_submission_archive.pulse_shared``), since that notice says the Pulse
carried one — and only a release that put a team request on the wall which was not on it: the
coordination editing a request already released is not news to the network, and a request typed
into the ficha is not announced on any project.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.shema_need import ShemaNeed
from app.models.shema_prayer import PrayerRelease
from app.services.notifications.get_shema_app_id import SHEMA_APP_KEY
from app.services.shema._consent import release_request
from app.services.shema._prayer_review import refuse_unless_coordination
from app.services.shema._redaction import log_reference
from app.services.shema._scope import Readership
from app.services.shema._submission_archive import pulse_shared
from app.services.shema._submission_notices import notify_shared_request
from app.services.shema.get_project import get_project

logger = logging.getLogger(__name__)


async def release_prayer_request(
    db: AsyncSession,
    readership: Readership,
    project_id: str,
    payload: PrayerRelease,
    *,
    user: User,
) -> None:
    """Release one request of ``project_id`` — its own, or the need ``payload.need_id`` names."""
    coordination = refuse_unless_coordination(
        readership, user=user, operation="release_prayer_request"
    )
    project = await get_project(
        db, coordination, project_id, user=user, operation="release_prayer_request"
    )
    need = None
    if payload.need_id is not None:
        need = (
            await db.execute(
                select(ShemaNeed).where(
                    ShemaNeed.project_id == project.id, ShemaNeed.id == payload.need_id
                )
            )
        ).scalar_one_or_none()
        if need is None:
            raise NotFoundError("Need not found")

    reached = release_request(project, need, reviewed=payload.reviewed, text=payload.text)
    if need is None and reached is not None and await pulse_shared(db, project, reached):
        await notify_shared_request(db, project, app_key=SHEMA_APP_KEY)
    await db.commit()
    logger.info(
        "shema prayer request released",
        extra={
            "shema_operation": "release_prayer_request",
            "shema_user_id": user.id,
            "shema_need_id": payload.need_id,
            "shema_edited": bool(payload.text and payload.text.strip() != payload.reviewed.strip()),
            **log_reference(project),
        },
    )
