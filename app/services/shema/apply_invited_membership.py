"""What accepting an invitation to a project's team does: the account joins it (OBT-547).

Called by ``resource_request_access.accept_invite`` for an invitation that names a project and
no role, inside its transaction. Confirming a project the mesa's approval filed invites every
proposed member with no account; the invitation is how that person gets one, and accepting it
is the membership OBT-524 writes — ``added_by`` the Admin who confirmed, as a grant accepted from
an invitation reads as the inviter's.

**Already a member is not a refusal.** The invitation promised a place on the team and the place
is there — an Admin may have added the account directly in the meantime — so the live row is
answered as it is and the invitation is spent.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_project_member import ShemaProjectMember
from app.services.shema._roster import seat_member


async def apply_invited_membership(
    db: AsyncSession, user_id: str, project_id: str, *, invited_by: str | None
) -> ShemaProjectMember:
    """Make ``user_id`` a live member of ``project_id``, or answer the live row it already has."""
    return await seat_member(db, project_id, user_id, added_by=invited_by)
