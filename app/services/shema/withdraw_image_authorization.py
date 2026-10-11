"""The coordination takes back the authorization of a photo — OBT-578's answer to its question 5.

Daniel, 8/oct/2026, by Karina's rule for the prayer request (1/oct/2026): withdrawing the
authorization **removes the image from the archived Pulse** that carried it — its reference,
its description and the leader's answer to the box — and stamps who and when; it does **not**
recall what already left, because nothing that left can be recalled (``docs/shema.md`` §9.3).

Two things happen in one transaction and neither alone: the item's decision becomes a refusal
(``_media_sharing.withdraw_authorization``), which is what every output path reads, and the
archive that carried the photo forgets it (``_submission_archive.erase_pulse_image``), which is
what a later apply of a pending Pulse reads. A photo that came to the record some other way has
no archive to clean, and only the decision moves.

**Withdraw, never grant.** The coordination may refuse what the team authorized; granting in
the team's place would be the server recording a consent nobody gave.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.shema_change_log import ChangeAction, ChangeSubject
from app.db.models.shema_form import ShemaIntakeImage, ShemaSubmission
from app.db.models.shema_media import ShemaMediaItem
from app.services.shema import _trail
from app.services.shema._audit import author_name
from app.services.shema._media_sharing import withdraw_authorization
from app.services.shema._redaction import log_reference
from app.services.shema._scope import RegionScope
from app.services.shema._submission_archive import erase_pulse_image
from app.services.shema.get_project import get_project

logger = logging.getLogger(__name__)


async def withdraw_image_authorization(
    db: AsyncSession, scope: RegionScope, project_id: str, item_id: str, *, user: User
) -> ShemaMediaItem:
    """Refuse the sharing of one photo, and take it out of the Pulse that brought it."""
    project = await get_project(
        db, scope, project_id, user=user, operation="withdraw_image_authorization"
    )
    stmt = select(ShemaMediaItem).where(
        ShemaMediaItem.project_id == project.id, ShemaMediaItem.id == item_id
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Media item not found")

    if withdraw_authorization(item, by=author_name(user)):
        _trail.stage(
            db,
            actor=user,
            subject=ChangeSubject.MEDIA,
            action=ChangeAction.WITHDRAWN,
            subject_id=item.id,
            project_id=project.id,
            region_key=_trail.region_value(project.region_key),
            fields=("authorization",),
        )
    image = (
        await db.execute(select(ShemaIntakeImage).where(ShemaIntakeImage.media_item_id == item.id))
    ).scalar_one_or_none()
    if image is not None and image.submission_id is not None:
        submission = await db.get(ShemaSubmission, image.submission_id)
        if submission is not None:
            await erase_pulse_image(db, submission, user=user)
    await db.commit()
    logger.info(
        "shema media authorization withdrawn",
        extra={
            "shema_operation": "withdraw_image_authorization",
            "shema_user_id": user.id,
            "shema_media_item_id": item.id,
            **log_reference(project),
        },
    )
    return item
