from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App

SHEMA_APP_KEY = "shema"


async def get_shema_app_id(db: AsyncSession) -> str:
    """The ``apps.id`` of Shemá, for ``notifications.app_id``.

    Fourth of its shape, beside ``get_mm_app_id``, ``get_oc_app_id`` and ``get_rr_app_id``,
    and deliberately identical to all three: ``notifications`` is multi-app, every row carries
    the app it belongs to, and each application resolves its own id here rather than each
    caller joining ``apps`` by key. ``docs/shema.md`` §4.6 names this file as BE-15's; BE-12
    needed it first — a submission that notifies nobody is the failure OBT-401 spends a
    paragraph on — and BE-15 inherits it, which is the whole reason its branch stacks on this
    one.

    The key is written a second time in this repository — ``app/api/shema/_deps.py`` is where
    the module names it, and ``test_the_app_key_is_named_once_in_the_module`` keeps it named
    once *inside* the module. This file is outside the module, in the package that serves
    eight applications, and the three siblings above set the shape. What keeps the pair honest
    is ``tests/test_shema/test_forms.py::test_the_app_key_here_is_the_modules_own``, which
    asserts this constant against ``_deps.APP_KEY`` so the two cannot drift apart in silence.
    """
    stmt = select(App.id).where(App.app_key == SHEMA_APP_KEY)
    result = await db.execute(stmt)
    app_id = result.scalar_one_or_none()
    if app_id is None:
        raise RuntimeError(f"App '{SHEMA_APP_KEY}' not found in database")
    return app_id
