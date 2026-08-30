from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import AccessRequest, App, User
from app.services.access_request._default_roles import default_role_for
from app.services.app.get_app_or_404 import get_app_or_404
from app.services.authorization.grant_app_role import grant_app_role


async def update_app(
    db: AsyncSession,
    app_id: str,
    name: str | None = None,
    description: str | None = None,
    icon_url: str | None = None,
    app_url: str | None = None,
    ios_url: str | None = None,
    android_url: str | None = None,
    platforms: Sequence[str] | None = None,
    is_active: bool | None = None,
    auto_approve: bool | None = None,
    actor: User | None = None,
) -> App:
    app = await get_app_or_404(db, app_id)
    if name is not None:
        app.name = name
    if description is not None:
        app.description = description
    if icon_url is not None:
        app.icon_url = icon_url
    if app_url is not None:
        app.app_url = app_url
    if ios_url is not None:
        app.ios_url = ios_url
    if android_url is not None:
        app.android_url = android_url
    if platforms is not None:
        app.platforms = list(platforms)
    if is_active is not None:
        app.is_active = is_active

    just_turned_on = auto_approve is True and not app.auto_approve
    if auto_approve is not None:
        app.auto_approve = auto_approve

    if just_turned_on:
        await _approve_pending_requests_for_app(db, app, actor=actor)

    await db.commit()
    await db.refresh(app)
    return app


async def _approve_pending_requests_for_app(
    db: AsyncSession, app: App, *, actor: User | None
) -> None:
    role_key = default_role_for(app.app_key)
    now = datetime.now(UTC)
    actor_id = actor.id if actor is not None else None

    pending_rows = await db.execute(
        select(AccessRequest).where(
            AccessRequest.app_id == app.id,
            AccessRequest.status == "pending",
        )
    )
    for request in pending_rows.scalars().all():
        request.status = "approved"
        request.reviewed_by = actor_id
        request.reviewed_at = now
        request.review_reason = "auto-approved (retroactive)"
        await grant_app_role(
            db, request.user_id, app.app_key, role_key, granted_by=actor_id, commit=False
        )
