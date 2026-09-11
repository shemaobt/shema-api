"""Taking a link back — the third word of the line this credential is judged by.

**Revocation is a timestamp and not a delete**, for the reason BE-02's column docstring gives:
*when* is the question a later reader asks, and a row that is gone cannot answer it. It is also
what lets a submission that arrived through a revoked link keep pointing at something — the
archive records how an answer reached the server, and erasing the link would erase that.

**Revoking twice is not an error.** A coordinator who taps revoke on a bad connection and taps
it again is asking for one thing, and the answer both times is the link, revoked. What is
refused is revoking a link the caller cannot reach, which is refused the way everything
out of scope in this module is: indistinguishably from a link that does not exist.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaFormDefinition, ShemaIntakeLink
from app.models.shema_forms import IntakeLink
from app.services.shema._intake_tokens import expires_on, link_status
from app.services.shema._scope import RegionScope, refuse_out_of_scope, visible_projects
from app.utils.stored_time import as_utc


async def revoke_intake_link(
    db: AsyncSession, scope: RegionScope, link_id: str, *, user: User
) -> IntakeLink:
    """Close one link now, whatever its clock says, and answer what it looks like closed."""
    row = (
        await db.execute(
            select(ShemaIntakeLink, ShemaFormDefinition.version)
            .join(ShemaFormDefinition, ShemaFormDefinition.id == ShemaIntakeLink.definition_id)
            .join(ShemaProject, ShemaProject.id == ShemaIntakeLink.project_id)
            .where(ShemaIntakeLink.id == link_id)
            .where(ShemaProject.id.in_(select(visible_projects(scope).subquery().c.id)))
        )
    ).first()
    if row is None:
        raise refuse_out_of_scope(
            scope, user=user, operation="revoke_intake_link", project_id=link_id
        )

    link, version = row
    if link.revoked_at is None:
        link.revoked_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(link)

    return IntakeLink(
        id=link.id,
        project_id=link.project_id,
        definition_version=version,
        expires_at=expires_on(link),
        status=link_status(link),
        created_at=as_utc(link.created_at).date(),
        used_at=None if link.used_at is None else as_utc(link.used_at).date(),
        revoked_at=None if link.revoked_at is None else as_utc(link.revoked_at).date(),
    )
