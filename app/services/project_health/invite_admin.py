from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.models.project_health import AdminInviteResponse
from app.services.authorization.grant_app_role import grant_app_role

logger = logging.getLogger(__name__)

PH_APP_KEY = "project-health"
PH_ADMIN_ROLE = "admin"


async def invite_admin(
    db: AsyncSession, *, email: str, invited_by_user_id: str
) -> AdminInviteResponse:
    """Grant the project-health admin role to an existing user identified by
    email. Raises NotFoundError if no user with that email exists yet — the
    invitee must sign up first, then be invited again.

    Both log lines name the accounts by id and never the address typed in: every ``extra``
    field is printed (``app/core/logging.py``), and an address is personal data the reader of a
    log has no business holding. The event's name rides as ``ph_event``, because ``event`` is
    the line's own message and an extra by that name would replace it."""
    normalized = email.lower()
    stmt = select(User).where(User.email == normalized)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        logger.info(
            "project_health.invite_admin denied: no user with that email",
            extra={
                "ph_event": "ph_invite_admin_denied",
                "actor_user_id": invited_by_user_id,
                "reason": "user_not_found",
            },
        )
        raise NotFoundError(
            "No user with that email has signed up yet. Ask them to sign up at "
            "the project-health login page first, then invite them again."
        )

    assignment = await grant_app_role(
        db,
        user.id,
        PH_APP_KEY,
        PH_ADMIN_ROLE,
        granted_by=invited_by_user_id,
    )
    logger.info(
        "project_health.invite_admin granted",
        extra={
            "ph_event": "ph_invite_admin_granted",
            "actor_user_id": invited_by_user_id,
            "target_user_id": user.id,
            "assignment_id": assignment.id,
        },
    )
    return AdminInviteResponse(
        email=user.email,
        pre_approved_role=PH_ADMIN_ROLE,
        access_request_id=assignment.id,
        granted=True,
    )
