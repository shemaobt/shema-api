from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.db.models.auth import App


async def create_app(
    db: AsyncSession,
    app_key: str,
    name: str,
    description: str | None = None,
    icon_url: str | None = None,
    app_url: str | None = None,
    ios_url: str | None = None,
    android_url: str | None = None,
    platforms: Sequence[str] | None = None,
    is_active: bool = True,
    auto_approve: bool = False,
) -> App:
    """Register an app, defaulting an unstated platform list to web-only.

    ``platforms=[]`` is refused rather than quietly replaced with ``["web"]``. The
    substitution was the earlier behaviour and it discarded what the caller asked for; an app
    with no platform is not a state this domain has — ``AppCreate`` and ``AppUpdate`` both
    carry ``min_length=1``, so the rule was already stated at the edge and only the services,
    reachable from seeds and scripts, could still write around it.
    """
    if platforms is not None and not platforms:
        raise ValidationError("platforms must name at least one platform")

    existing = await db.execute(select(App).where(App.app_key == app_key))
    if existing.scalar_one_or_none():
        raise ConflictError(f"App with key '{app_key}' already exists")

    app = App(
        app_key=app_key,
        name=name,
        description=description,
        icon_url=icon_url,
        app_url=app_url,
        ios_url=ios_url,
        android_url=android_url,
        platforms=list(platforms) if platforms is not None else ["web"],
        is_active=is_active,
        auto_approve=auto_approve,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app
