from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App

RR_APP_KEY = "resource-request-form"


async def get_rr_app_id(db: AsyncSession) -> str:
    """The ``apps.id`` of the resource-request form, for ``notifications.app_id``.

    Third of its shape, beside ``get_mm_app_id`` and ``get_oc_app_id``, and deliberately
    identical to both: ``notifications`` is multi-app, every row carries the app it
    belongs to, and each application resolves its own id here rather than each caller
    joining ``apps`` by key.

    The key is written a second time in this repository — ``app/api/resource_requests/
    _deps.py`` is where the module names it, and a test keeps it named once *inside* the
    module. This file is outside the module, in the package that serves eight
    applications, and the two siblings above set the shape. What keeps the pair honest is
    ``test_notifications.py::test_the_app_key_here_is_the_module_s_own``, which asserts
    this constant against ``_deps.APP_KEY`` so the two cannot drift apart in silence.
    """
    stmt = select(App.id).where(App.app_key == RR_APP_KEY)
    result = await db.execute(stmt)
    app_id = result.scalar_one_or_none()
    if app_id is None:
        raise RuntimeError(f"App '{RR_APP_KEY}' not found in database")
    return app_id
