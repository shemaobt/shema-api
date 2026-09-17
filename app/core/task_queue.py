from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    import procrastinate

logger = logging.getLogger(__name__)

_app: procrastinate.App | None = None


def get_task_app() -> procrastinate.App:
    import procrastinate as proc

    global _app
    if _app is None:
        settings = get_settings()
        _app = proc.App(
            connector=proc.PsycopgConnector(
                conninfo=settings.database_url.replace("postgresql+asyncpg://", "postgresql://"),
            ),
            import_paths=["app.tasks"],
        )
    return _app


async def init_task_queue() -> None:
    try:
        app = get_task_app()
        await app.open_async()
        logger.info("Procrastinate task queue initialized")
    except Exception:
        logger.warning("Procrastinate initialization skipped (worker may not be running)")


async def close_task_queue() -> None:
    if _app is not None:
        with contextlib.suppress(Exception):
            await _app.close_async()
