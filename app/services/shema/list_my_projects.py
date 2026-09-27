"""``GET /api/shema/me/projects`` — the projects the caller is a live member of (OBT-524).

What the form and the *Solicitar recurso* button consume (OBT-520, OBT-544), and the whole of what a
member with no regional role reaches of the project list: ``_scope.member_projects`` is the
statement, and it reads live memberships and nothing else — a removed stay, somebody else's
membership and a project the caller merely has a region over are all absent.

Ordered by name, then id, so the list reads the same between calls. The ref carries no place: the
id and the language name are what a picker needs.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.models.shema_project_member import ProjectRef
from app.services.shema._scope import member_projects


async def list_my_projects(db: AsyncSession, user: User) -> list[ProjectRef]:
    """Every project ``user`` is a live member of, as a ``ProjectRef``."""
    stmt = member_projects(user.id).order_by(ShemaProject.language_name, ShemaProject.id)
    return [
        ProjectRef(id=project.id, languageName=project.language_name)
        for project in (await db.execute(stmt)).scalars()
    ]
