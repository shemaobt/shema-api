"""The roster's shared half: the live row of a pair, and the shape one row leaves in (OBT-524).

Three services read ``shema_project_members`` — the roster read, the add and the removal — and two
questions are asked by more than one of them: *is this account a live member of this project*, and
*what does a member look like on the wire*. Each has one answer, here, so the add's conflict check
and the removal's lookup cannot drift apart on what *live* means, and the add answers exactly the
shape the roster lists. OBT-547 adds a third: *seat this account unless it is already live* — what
confirming a filed project and accepting an invitation to its team both do, where a live row is
the outcome promised rather than a conflict.

Which projects a caller reaches is not here: that is ``_scope.py``'s, which owns the module's only
``select(ShemaProject)``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_project_member import MEMBER_ROLE, ShemaProjectMember
from app.models.shema_project_member import ProjectMember
from app.services.shema._audit import author_name
from app.utils.stored_time import as_utc


async def live_membership(
    db: AsyncSession, project_id: str, user_id: str
) -> ShemaProjectMember | None:
    """The live row of ``(project_id, user_id)``, or ``None`` — the partial index makes it one."""
    stmt = select(ShemaProjectMember).where(
        ShemaProjectMember.project_id == project_id,
        ShemaProjectMember.user_id == user_id,
        ShemaProjectMember.removed_at.is_(None),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def seat_member(
    db: AsyncSession, project_id: str, user_id: str, *, added_by: str | None
) -> ShemaProjectMember:
    """The live row of ``(project_id, user_id)``, written now if there was none. Flushed, never
    committed: the caller's act owns the transaction."""
    live = await live_membership(db, project_id, user_id)
    if live is not None:
        return live
    member = ShemaProjectMember(
        project_id=project_id, user_id=user_id, role=MEMBER_ROLE, added_by=added_by
    )
    db.add(member)
    await db.flush()
    return member


def project_member(member: ShemaProjectMember, account: User) -> ProjectMember:
    """One row and its account, as the roster shows them: who, as what, since which UTC day."""
    return ProjectMember(
        userId=member.user_id,
        name=author_name(account),
        role=member.role,
        addedAt=as_utc(member.added_at).date(),
    )
