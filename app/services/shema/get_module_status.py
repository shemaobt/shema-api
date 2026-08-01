import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.version import get_app_version
from app.models.shema import ShemaDatabaseStatus, ShemaHealthResponse

MODULE_NAME = "shema"
PROBE_TIMEOUT_SECONDS = 5.0


async def get_module_status(db: AsyncSession) -> ShemaHealthResponse:
    database: ShemaDatabaseStatus
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), PROBE_TIMEOUT_SECONDS)
        database = "ok"
    except (SQLAlchemyError, TimeoutError):
        database = "unavailable"

    return ShemaHealthResponse(
        module=MODULE_NAME,
        status="ok" if database == "ok" else "degraded",
        version=get_app_version(),
        database=database,
    )
