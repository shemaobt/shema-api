from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App

SHEMA_APP_KEY = "shema"


async def get_shema_app_id(db: AsyncSession) -> str:
    """The ``apps.id`` of Shemá, for ``notifications.app_id``.

    Fourth of its shape, beside ``get_mm_app_id``, ``get_oc_app_id`` and ``get_rr_app_id``,
    and deliberately identical to all three: ``notifications`` is multi-app, every row
    carries the app it belongs to, and each application resolves its own id here rather
    than each caller joining ``apps`` by key.

    ``docs/shema.md`` §1.3 C2 gives this file to BE-15, which builds the panel. **BE-08
    wrote it because the first notice is written before the first panel is read** — an
    urgent need has to reach somebody the moment it is raised, and a notice with no
    ``app_id`` has nowhere to be listed. BE-15 inherits it rather than adding it, and the
    same section's other half — ``get_oc_app_id`` existing on disk and missing from this
    package's ``__all__`` — is still somebody else's one-line change and is deliberately
    not made here.

    The key is written a second time in this repository: ``app/api/shema/_deps.py`` is
    where the module names it, and ``test_the_app_key_is_named_once_in_the_module`` keeps
    it named once *inside* the module. This file is outside the module, in the package
    that serves eight applications, and the three siblings above set the shape. What keeps
    the pair honest is ``tests/test_shema/test_needs.py::
    test_the_app_key_the_notifier_uses_is_the_module_s_own``, which asserts this constant
    against ``_deps.APP_KEY`` so the two cannot drift apart in silence — the check the
    sibling's ``test_notifications.py`` already makes for its own.
    """
    stmt = select(App.id).where(App.app_key == SHEMA_APP_KEY)
    result = await db.execute(stmt)
    app_id = result.scalar_one_or_none()
    if app_id is None:
        raise RuntimeError(f"App '{SHEMA_APP_KEY}' not found in database")
    return app_id
