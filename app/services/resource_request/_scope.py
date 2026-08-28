"""Which requests a caller reaches — the axis capabilities were never built to answer.

``edit_requests`` belongs to all three roles (GATE-02 D4: the mesa may edit what the team
wrote), so the capability says *may edit a request* and says nothing about **which** ones.
The frontend's table has no scope column and should not grow one: adding
``read_all_requests`` would put a row the client never saw into contract §5.3, which is a
client artefact.

So this is the one place in the module that reads a **role** rather than a capability, and
it reads it for a scope rather than for a permission. The rule is the narrow one: a caller
who is only ``equipe`` reaches the requests it authored, and anyone else reaches all of
them. Stated as *only equipe* and not as *is mesa or gestor* so that a fourth role — the
Líder de Base of BE-16 — does not silently inherit the team's narrow view before anyone has
decided what he should see.

A platform admin reaches everything, as they pass every other guard in this module
unconditionally (``require_capability`` in ``_deps.py`` says the same, with the reason).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.services import authorization_service

TEAM_ROLE = "equipe"


async def reaches_every_request(db: AsyncSession, user: User, app_key: str) -> bool:
    """Whether this caller sees the whole board's worth of requests, or only its own."""
    if user.is_platform_admin:
        return True

    granted = {
        role_key
        for _app_key, role_key in await authorization_service.list_roles(db, user.id, app_key)
    }
    return bool(granted - {TEAM_ROLE})
