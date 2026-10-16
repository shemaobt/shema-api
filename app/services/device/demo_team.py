"""The demo team (ADR 0064): the one team per environment named by configuration, by its id.

With no configuration there is no demo team, and a configured id that names no team is no
demo team either.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.project import Project

logger = logging.getLogger(__name__)


def is_the_demo_team(project_id: str | None) -> bool:
    configured = get_settings().internalization_room_demo_team_id
    return bool(configured) and project_id == configured


async def the_demo_team(db: AsyncSession) -> str | None:
    """The demo team's id, once it names a team that exists."""
    configured = get_settings().internalization_room_demo_team_id
    if not configured:
        return None
    if await db.get(Project, configured) is None:
        logger.warning("demo team not found", extra={"demo_team_id": configured})
        return None
    return configured
