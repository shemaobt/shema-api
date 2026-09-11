"""The links a coordinator has out, so that *revocable* is something they can act on.

A revocation endpoint with no way to find the id is a revocation endpoint that is used once,
by whoever still has the creation response open. This is the other half of it, and it is
scoped like every read in this module: the links of the projects the caller can reach.

**No token, ever.** The listing carries the id, the project, the version, the dates and the
state. A listing that handed the token back would make *revoked* a word rather than a fact,
because the credential would still be readable by anybody who can read the list — which is a
wider set than the one person it was handed to.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaFormDefinition, ShemaIntakeLink
from app.models.shema_forms import IntakeLink
from app.services.shema._intake_tokens import expires_on, link_status
from app.services.shema._scope import RegionScope, visible_projects
from app.utils.stored_time import as_utc


async def list_intake_links(
    db: AsyncSession, scope: RegionScope, *, project_id: str | None = None
) -> list[IntakeLink]:
    """Every link on a project the caller reaches, newest first.

    The scope is applied by joining the links to ``visible_projects`` rather than by filtering
    them afterwards: the predicate is underneath the query instead of beside it, which is
    ``_scope.py``'s own reason for handing out a ``Select`` and is what stops a later ``LIMIT``
    from paging past a scope.

    ``project_id`` narrows and never widens — an id outside the scope simply matches nothing,
    which is the same *indistinguishable from absent* answer a direct read gives.
    """
    reachable = visible_projects(scope).with_only_columns(ShemaProject.id).subquery()
    stmt = (
        select(ShemaIntakeLink, ShemaFormDefinition.version)
        .join(ShemaFormDefinition, ShemaFormDefinition.id == ShemaIntakeLink.definition_id)
        .where(ShemaIntakeLink.project_id.in_(select(reachable.c.id)))
        .order_by(ShemaIntakeLink.created_at.desc())
    )
    if project_id is not None:
        stmt = stmt.where(ShemaIntakeLink.project_id == project_id)

    return [
        IntakeLink(
            id=link.id,
            project_id=link.project_id,
            definition_version=version,
            expires_at=expires_on(link),
            status=link_status(link),
            created_at=as_utc(link.created_at).date(),
            used_at=None if link.used_at is None else as_utc(link.used_at).date(),
            revoked_at=None if link.revoked_at is None else as_utc(link.revoked_at).date(),
        )
        for link, version in (await db.execute(stmt)).all()
    ]
